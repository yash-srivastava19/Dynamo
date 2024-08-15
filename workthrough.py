# This is a the initial draft of what I came up with ; this is static load balancer from scratch.

import argparse

class Service:
    def __init__(self, budget: int):
        self.budget = budget
        self.capacity = None # will be used later.

class TrafficBalancer:
    def __init__(self, service: Service) -> None:
        self.load = service.budget
        self.services = [service]

    def throw_traffic(self, num_requests: int) -> int:
        # based on the budget, handle the traffic
        if num_requests < self.load:
            # then one service is more than enough
            return len(self.services) # num workers.
        
        total_budget = self.load # we start off with the initial service load. 
        while num_requests > total_budget:
            new_service = Service(self.load)
            total_budget += self.load
            self.services.append(new_service)
        
        return len(self.services)
    
    def distribute_traffic(self, num_requests):
        num_services = self.throw_traffic(num_requests=num_requests) # populates the service.
        # Distribute the num_requests among num_services. Try to do it equally, if not we'll... .
        if num_requests % num_services == 0:
            for service in self.services:
                service.capacity = num_requests // num_services
        else: # not distributing equally.
            # First, we'll get the traffic that si remanining,the closest to which we can distribute.
            remaining =  num_requests % num_services
            # we can give it randomly to any one of the service
            import random 
            r_service = random.choice(self.services)
            r_service.capacity += remaining
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="A simple Load Balancer.")
    parser.add_argument("--budget", required=True)
    parser.add_argument("--requests", required=True)

    args = parser.parse_args()
    service = Service(int(args.budget))
    tb = TrafficBalancer(service)

    tb.distribute_traffic(int(args.requests))
    for i, service in enumerate(tb.services):
        print(f"Service: {i+1}, Capacity: {service.capacity}")
