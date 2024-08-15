import time
import random
import threading
import logging
from typing import List, Dict, Any
from abc import ABC, abstractmethod
import mysql.connector
from flask import Flask, request, jsonify
import requests
from concurrent.futures import ThreadPoolExecutor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Service(ABC):
    def __init__(self, service_id: str, cost: float):
        self.service_id = service_id
        self.cost = cost
        self.load = 0

    @abstractmethod
    def process_request(self, request):
        pass

    def get_load(self) -> int:
        return self.load

class WebServer(Service):
    """ A web service that we are going to scale horizontally. """
    def __init__(self, service_id: str, port: int, cost: float = 10):
        super().__init__(service_id, cost)
        self.app = Flask(__name__)
        self.port = port

        @self.app.route('/process', methods=['POST'])
        def process():
            data = request.json
            result = f"Processed by WebServer {self.service_id}: {data['request']}"
            self.load += 1
            return jsonify({"result": result})

    def start(self):
        threading.Thread(target=self.app.run, kwargs={'host': '0.0.0.0', 'port': self.port}, daemon=True).start()

    def process_request(self, request):
        """ Bottleneck operation, so we scale horizontally based on the response from this function. """
        response = requests.post(f"http://localhost:{self.port}/process", json={"request": request})
        return response.json()['result']

class Database(Service):
    """ A database service that we are going to scale horizontally. """
    def __init__(self, service_id: str, host: str, user: str, password: str, database: str, cost: float = 20):
        super().__init__(service_id, cost)
        self.connection = mysql.connector.connect(
            host=host,
            user=user,
            password=password,
            database=database
        )
        self.cursor = self.connection.cursor()

        # Just a random table to test whether things work or not.
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                id INT AUTO_INCREMENT PRIMARY KEY,
                request_data TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.connection.commit()

    def process_request(self, request)
        """For database operations, this is the bottleneck, so we scale horizontally based on the response from this function. """
        # Write request to the newly created database
        self.cursor.execute("INSERT INTO requests (request_data) VALUES (%s)", (str(request),))
        self.connection.commit()

        # Read from the created database
        self.cursor.execute("SELECT * FROM requests ORDER BY id DESC LIMIT 1")
        result = self.cursor.fetchone()

        self.load += 1
        return f"Database query processed by {self.service_id}: {result}"

class LoadBalancer:
    """A simple implementation of a load balancer. Static balancing as of now, but we'll  see how to do the dynamic one as well."""
    def __init__(self, services):
        self.services = services
        self.last_service_index = -1

    def distribute_request(self, request):
        """ Given any request, we allocate/distribute it to a particular service to process."""
        if not self.services:
            raise Exception("No services available")

        self.last_service_index = (self.last_service_index + 1) % len(self.services)
        service = self.services[self.last_service_index]
        return service.process_request(request)

class BudgetConstrainedAutoScaler:
    """A budget based autoscaler to simulate real-life scenarios. """
    def __init__(self, web_servers: List[WebServer], databases: List[Database], 
                 total_budget: float, 
                 web_server_factory: callable, database_factory: callable,
                 scale_up_threshold: int = 10, scale_down_threshold: int = 5):
        self.web_servers = web_servers
        self.databases = databases
        self.total_budget = total_budget
        self.web_server_factory = web_server_factory
        self.database_factory = database_factory
        self.scale_up_threshold = scale_up_threshold
        self.scale_down_threshold = scale_down_threshold

    def check_and_scale(self):
        """This is the event loop function. We'll call this repetedly and check whether the resources are suffic or not."""
      
        total_load = sum(server.get_load() for server in self.web_servers) + sum(db.get_load() for db in self.databases)
        avg_load = total_load / (len(self.web_servers) + len(self.databases)) if (self.web_servers or self.databases) else 0

        current_cost = sum(server.cost for server in self.web_servers) + sum(db.cost for db in self.databases)
        available_budget = self.total_budget - current_cost

        if avg_load > self.scale_up_threshold and available_budget > 0:
            if available_budget >= 20 and random.random() < 0.3:  # Does this number makes sense?
                new_db = self.database_factory()
                if new_db.cost <= available_budget:
                    self.databases.append(new_db)
                    logger.info(f"Scaling up. New database added: {new_db.service_id}")
            elif available_budget >= 10:
                new_server = self.web_server_factory()
                if new_server.cost <= available_budget:
                    self.web_servers.append(new_server)
                    new_server.start()
                    logger.info(f"Scaling up. New web server added: {new_server.service_id}")
        elif avg_load < self.scale_down_threshold and (len(self.web_servers) > 1 or len(self.databases) > 1):
            if self.web_servers and (len(self.databases) <= 1 or random.random() < 0.7):  # 70% chance to remove a web server
                removed_server = self.web_servers.pop()
                logger.info(f"Scaling down. Web server removed: {removed_server.service_id}")
            elif self.databases:
                removed_db = self.databases.pop()
                logger.info(f"Scaling down. Database removed: {removed_db.service_id}")

        logger.info(f"Current setup: {len(self.web_servers)} web servers, {len(self.databases)} databases. " 
                    f"Avg load: {avg_load:.2f}, Available budget: {available_budget:.2f}")

class DynamicWebTier:
    """Think of this function as the service manager, which manages the services dynamically. """
    def __init__(self, total_budget: float, initial_web_servers: int = 2, initial_databases: int = 1):
        self.web_servers = [WebServer(f"WebServer-{i}", 5000 + i) for i in range(initial_web_servers)]
        self.databases = [Database(f"Database-{i}", "localhost", "user", "password", "testdb") for i in range(initial_databases)]
        
        for server in self.web_servers:
            server.start()

        # Flexible, we can use either or both. 
        self.web_lb = LoadBalancer(self.web_servers)
        self.db_lb = LoadBalancer(self.databases)
        
        self.auto_scaler = BudgetConstrainedAutoScaler(
            self.web_servers, 
            self.databases, 
            total_budget,
            lambda: WebServer(f"WebServer-{random.randint(1000, 9999)}", random.randint(5000, 6000)),
            lambda: Database(f"Database-{random.randint(1000, 9999)}", "localhost", "user", "password", "testdb")
        )

        self.scaling_thread = threading.Thread(target=self._run_auto_scaler, daemon=True)
        self.scaling_thread.start()

    def _run_auto_scaler(self):
        while True:
            self.auto_scaler.check_and_scale()
            time.sleep(5)  # Check scaling every 5 seconds ; in real scenarios, this might be different.

    def process_request(self, request):
        web_response = self.web_lb.distribute_request(request)
        db_response = self.db_lb.distribute_request(request)
        return f"{web_response} -> {db_response}"

def simulate_traffic(web_tier: DynamicWebTier, duration: int, max_requests_per_second: int):
    """ Instead of actual traffic, we simulate traffic through this proxy function. """
    start_time = time.time()
    request_count = 0

    with ThreadPoolExecutor(max_workers=100) as executor:
        while time.time() - start_time < duration:
            requests_this_second = random.randint(1, max_requests_per_second)
            futures = []
            for i in range(requests_this_second):
                futures.append(executor.submit(web_tier.process_request, f"Request-{request_count}"))
                request_count += 1
            for future in futures:
                result = future.result()
                logger.debug(result)
            time.sleep(1)

    logger.info(f"Simulation complete. Processed {request_count} requests in {duration} seconds.")

if __name__ == "__main__":
    total_budget = 100  # Total budget for all services
    simulation_duration = 300  # 5 minutes
    max_requests_per_second = 20

    web_tier = DynamicWebTier(total_budget)
    simulate_traffic(web_tier, simulation_duration, max_requests_per_second)
