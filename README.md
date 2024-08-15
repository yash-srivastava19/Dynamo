# Dynamo - Implementing Load Balancer and Autoscaler.
A simple implementation of a load balancer and autoscaler from scratch(in Python and Rust) to simulate a MySQL web tier.

## Project
This project is an attempt to simulate a web-tier which we scale horizontally using load balancer and autoscaler. Before proceeding further, read the next sections to get the sense of why solving this problem is important.

For the initial draft, I implemented a simple load balancer, which at its core does only this-
1. Distribute traffic to service.

Well, that is easy to prototype. Here's what I came up with
```
class LoadBalancer:
...
  def distribute_traffic(self, num_requests):
          num_services = self.throw_traffic(num_requests=num_requests) # populates the service.
          # Distribute the num_requests among num_services. Try to do it equally... .
          if num_requests % num_services == 0:
              for service in self.services:
                  service.capacity = num_requests // num_services
          else: # not distributing equally.
              # First, we'll get the traffic that is remanining,the closest to which we can distribute.
              remaining =  num_requests % num_services
              # we can give it randomly to any one of the service
              import random 
              r_service = random.choice(self.services)
              r_service.capacity += remaining
```
The `throw_traffic` simulates incoming traffic to any service. If the number of services can be equally divided among the services, we'll do that. Otherwise, we can just randomly give the remaining to any service. Each service has a specific capacity, and we cannot exceed it.

This was a great step in the right direction. Next, was understanding how static load balancing works. Static means that the maximum and minimum compute requirements need to be known beforehand. There are many load balancing algorithm to distribute traffic we could've used here, I chose round robin and least connection. Here's how we distribute the traffic in a static load balancer:

```
class LoadBalancer:

...

  def distribute_request(self, request: Any) -> Any:
          """Given any request, we allocate/distribute it to a particular service to process."""
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

```
Here's a short description of what both of those methods do:
1. **Round Robin:** Select the service in a circular manner. If service 1 is not available, move to service 2 and so on, and cycle back to the 1 one if the last service is unavailable.
2. **Least Connection:** Select the service which has the minimum load. 

Finally, we move towards dynamic scaling. This is where we try to mimic real life setting. In dynamic case, the compute resouces are inferred at run-time, and the constraint we have is the "compute budget". Here's how the Autoscaler implements the `check_and_scale` function, which we call repeatedly and horizontally upscale or downscale the system.

```
class AutoScaler:

...
  def check_and_scale(self):
          total_load = sum(server.get_load() for server in self.web_servers) + sum(db.get_load() for db in self.databases)
          avg_load = total_load / (len(self.web_servers) + len(self.databases)) if (self.web_servers or self.databases) else 0
  
          current_cost = sum(server.cost for server in self.web_servers) + sum(db.cost for db in self.databases)
          available_budget = self.total_budget - current_cost
  
          if avg_load > self.scale_up_threshold and available_budget > 0:
              if available_budget >= 20 and random.random() < 0.3:  # 30% chance to add a database if budget allows
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
  
```

The next task is to implement this in Rust, and make full use of the fearless concurrency provided in it. Read the next sections to grasp why exactly we need to solve this problem.

## Motivation
Running cloud services is not an easy task. The journey from zero to million users is very complicated, and is a great lesson in understanding the dynaics of scale up. I was recently reading the System Design Book by Alex Xu, and being an avid minecraft and factorio watcher(I honestly don't have time to play :( ), I found some parallels in the way Autoscaler and Load Balancer works. One of the best ways in which I learn any concept is:

1. Read all the relevant materials, and enough tounderstand the core logic behind the tool
2. Try implementing a toy version of the tool, and explain it in great detail.
3. Iterate and improve.

I've been learning a lot about concurrency in Python, and implementing a load balancer and autoscaler was challenging enough project. I've been planning to mirror the implementation in Rust(future update) as well.

## Why Scale ?
Whatsapp, Twitter, Youtube

What's the one thing these products have that make them so good? For me, the answer is their availability(though it is true for any content application). FOr products such as those mentioned, even a small downtime could be easily potential million dollars worth. Designing products that support millions of users is challenging, and requires continuous improvements and optimizations. 

There are mainly two types of scaling, horizontal and vertical
1. Vertical Scaling refers to the process of adding more compute power(RAM, GPU) to your servers.
2. Horizontal Scaling refers to the process of adding more servers into your pool of resouces.

Horizontal scaling is more desireable for large scale application, but we can't just keep adding more servers, we need this process to be economically viable. How should we do it?

## Load Balancer
When the number of users are low, we can directly allow users to connect to the web server. As the number of users increase, if all the users access the service at the same time, we can reach the connection limit of the server, and we might get downtime(a bad deal from economic point of view).

Load balancer is a tool which addresses this issue. A load balancer evenly distributes the traffic among servers. The users connect to the load balancer, and the load balancer communicates with the servers. If one of the server goes offline, the traffic will be routed to another server(based on some distribution algorithm)

There is, however, one small issue. If we went ahead with this approach, we need to pre-estimate how many servers we need for our application to run smoothly. Running servers cost money. If we over-estimate, we will have a huge spend on cloud bills. If we underestimate, users might face downtime and you could lose customers. How do we deal with this problem?

## Autoscaler
The answer is autoscaler. Autoscaling is a way to automatically scale the computing resources(servers) based on the load. An autoscaler can scale up the number of resources when there is a spike in web-traffic, and scales down when traffic levels are low. All major cloud computing vendors offers autoscaling services. 

Apart from economic utility of the autoscaler, it also helps reduce carbon emissions!! This process conserves energy by putting idle servers to sleep when the load is low. Even the electricity bill is reduced!! 

