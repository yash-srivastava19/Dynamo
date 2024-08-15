import time
import random
import threading
import logging
from typing import List, Callable, Dict, Any
from abc import ABC, abstractmethod

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Service(ABC):
    def __init__(self, service_id: str):
        self.service_id = service_id
        self.load = 0

    @abstractmethod
    def process_request(self, request: Any) -> Any:
        pass

class LoadBalancer:
    """A simple implementation of a load balancer. Static balancing as of now, but we'll  see how to do the dynamic one as well."""
    def __init__(self, distribution_algorithm: str = "round_robin"):
        self.services: List[Service] = []
        self.distribution_algorithm = distribution_algorithm
        self.last_service_index = -1

    def add_service(self, service: Service):
        self.services.append(service)
        logger.info(f"Added service: {service.service_id}")

    def remove_service(self, service: Service):
        self.services.remove(service)
        logger.info(f"Removed service: {service.service_id}")

    def distribute_request(self, request: Any) -> Any:
        """Really important to understand this function. Given any request, we allocate/distribute it to a particular service to process."""
        if not self.services:
            raise Exception("No services available")

        # If our algo is round robin, we get the service in a circular based manner(round robin). 
        if self.distribution_algorithm == "round_robin":
            self.last_service_index = (self.last_service_index + 1) % len(self.services)  # this is OK, but can we do a master-slave thing?
            service = self.services[self.last_service_index]
        
        # If our algo is least connection, we get the service which has the minimun load.
        elif self.distribution_algorithm == "least_connections":
            service = min(self.services, key=lambda s: s.load)
        
        else:
            raise ValueError(f"Unknown distribution algorithm: {self.distribution_algorithm}")

        result = service.process_request(request)
        service.load += 1 # really important to do this, otherwise we'll be stuck in a loop.
        return result

class AutoScaler:
    """Base class to autoscale services based requirements. """
    def __init__(self, load_balancer: LoadBalancer, min_services: int, max_services: int, 
                 scale_up_threshold: int, scale_down_threshold: int, 
                 service_factory: Callable[[], Service]):
        
        # Providing min/max threshold makes this a static auto-scaler. We would like to do this dynamically[with constraints]
        self.load_balancer = load_balancer
        self.min_services = min_services
        self.max_services = max_services
        self.scale_up_threshold = scale_up_threshold
        self.scale_down_threshold = scale_down_threshold
        self.service_factory = service_factory

    def check_and_scale(self):
        """This is the event loop function. We'll call this repetedly and check whether the resources are suffic or not."""

        # The end goal is to make this function dynamic. We'll see how to do that.
        total_load = sum(service.load for service in self.load_balancer.services)
        avg_load = total_load / len(self.load_balancer.services) if self.load_balancer.services else 0

        if avg_load > self.scale_up_threshold and len(self.load_balancer.services) < self.max_services:
            new_service = self.service_factory()
            self.load_balancer.add_service(new_service)
            logger.info(f"Scaling up. New service added. Total services: {len(self.load_balancer.services)}")
        
        elif avg_load < self.scale_down_threshold and len(self.load_balancer.services) > self.min_services:
            service_to_remove = self.load_balancer.services[-1]
            self.load_balancer.remove_service(service_to_remove)
            logger.info(f"Scaling down. Service removed. Total services: {len(self.load_balancer.services)}")

class DynamicServiceManager:
    def __init__(self, service_factory: Callable[[], Service], 
                 min_services: int = 2, max_services: int = 5, 
                 scale_up_threshold: int = 10, scale_down_threshold: int = 5, 
                 distribution_algorithm: str = "round_robin"):
        
        self.load_balancer = LoadBalancer(distribution_algorithm)
        self.auto_scaler = AutoScaler(self.load_balancer, min_services, max_services, 
                                      scale_up_threshold, scale_down_threshold, service_factory)
        
        for _ in range(min_services):
            self.load_balancer.add_service(service_factory())

        self.scaling_thread = threading.Thread(target=self._run_auto_scaler, daemon=True)
        self.scaling_thread.start()

    def _run_auto_scaler(self):
        while True:
            self.auto_scaler.check_and_scale()
            time.sleep(5)  # Check scaling every 5 seconds

    def process_request(self, request: Any) -> Any:
        return self.load_balancer.distribute_request(request)

class TestService(Service):
    def process_request(self, request: Any) -> Any:
        # Other things are implemented, just need to implement this function.
        time.sleep(random.uniform(0.1, 0.5))  # Simulating processing time
        return f"Processed by {self.service_id}: {request}"


def test_service_factory() -> Service:
    """A function that returns the service is a service factory."""
    return TestService(f"Service-{random.randint(1000, 9999)}")

if __name__ == "__main__":
    manager = DynamicServiceManager(test_service_factory)

    for i in range(100):
        result = manager.process_request(f"Request-{i}")
        logger.info(result)
        time.sleep(0.1)
