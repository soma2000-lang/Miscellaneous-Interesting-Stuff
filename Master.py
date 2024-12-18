import grpc
from concurrent import futures
import map_reduce_pb2
import map_reduce_pb2_grpc
import subprocess
import argparse
import random
import socket
import time
import os
import threading
import shutil

class Master(map_reduce_pb2_grpc.MasterServiceServicer):
    def __init__(self, mappers, reducers, centroids, max_iterations, portNo, data_path):
        self.num_mappers = mappers
        self.num_reducers = reducers
        self.num_centroids = centroids
        self.max_iterations = max_iterations
        self.indices_per_mapper = {}
        self.mapper_ports = []
        self.reducer_ports = []
        self.mapper_port_id = {}
        self.reducer_port_id = {}
        self.centroids = []
        self.data_path = data_path
        self.portNo = portNo
        self.ip = socket.gethostbyname(socket.gethostname())
        self.pairs = []

        for i in range(self.num_mappers):
            self.mapper_ports.append(self.portNo+i+1)
        for i in range(self.num_reducers):
            self.reducer_ports.append(self.mapper_ports[-1]+i+1)
    def invoke_mappers(self):
        mapper_id = 0
        for i in self.mapper_ports:
            subprocess.Popen(["python3", "Mapper.py", "--mapperId", f"{mapper_id}", "--portNo", f"{i}", "--numReducers", f'{self.num_reducers}'])
            self.mapper_port_id[i] = mapper_id
            mapper_id += 1
        time.sleep(5)
        dump_master = open("./dump_master.txt", "a")
        dump_master.write(f"Mappers Started at port numbers: {self.mapper_ports}\n")
        dump_master.close()
        print("Mappers Started at port numbers:", self.mapper_ports)
    
    def invoke_reducers(self):
        reducer_id = 0
        # print(' '.join(str(x) for x in self.mapper_ports))
        for i in self.reducer_ports:
            subprocess.Popen(["python3", "Reducer.py", "--reducerId", f"{reducer_id}", "--portNo", f"{i}", "--mappers", f"{' '.join(str(x) for x in self.mapper_ports)}"])
            self.reducer_port_id[i] = reducer_id
            reducer_id += 1
        time.sleep(5)
        dump_master = open("./dump_master.txt", "a")
        dump_master.write(f"Reducers Started at port numbers: {self.reducer_ports}\n")
        dump_master.close()
        print("Reducers Started", self.reducer_ports)

    def input_split(self):
        file = open(self.data_path, "r")
        data_points = file.read().split("\n")
        data_points = [map_reduce_pb2.Point(x=float(point.split(",")[0]), y=float(point.split(",")[1])) for point in data_points]
        # print(data_points)
        file.close()
        indices_per_mapper = {}
        for i in range(self.num_mappers):
            indices_per_mapper[i] = []
        for i in range(len(data_points)):
            index = i%self.num_mappers
            indices_per_mapper.get(index).append(i)

        self.indices_per_mapper = indices_per_mapper
        self.centroids = random.sample(data_points, self.num_centroids)
        dump_master = open("./dump_master.txt", "a")
        dump_master.write(f"Randomly Initialized Centroids:\n")
        for centroid in self.centroids:
            dump_master.write(f"{centroid.x}, {centroid.y}\n")
        dump_master.close()
    
    def SendMapperData(self, request, context):
        data_indices = self.indices_per_mapper[request.mapper_id]
        centroids = self.centroids
        return map_reduce_pb2.MapDataResponse(input_split=data_indices, centroids=centroids, input_path=self.data_path)

    def sendMapperData(self):
        threads = []
        for mapper_port_id in range(len(self.mapper_ports)):
            thread = threading.Thread(target=self.threadedSendMapperData, args=(mapper_port_id,))
            thread.start()
            threads.append(thread)

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

    def threadedSendMapperData(self, mapper_port_id):
        channel = grpc.insecure_channel(self.ip + ":" + str(self.mapper_ports[mapper_port_id]))
        stub = map_reduce_pb2_grpc.MapperServiceStub(channel)
        indices = self.indices_per_mapper[mapper_port_id]
        request = map_reduce_pb2.MapDataRequest(input_split=indices, centroids=self.centroids, input_path=self.data_path)
        try:
            print(f"Sending grpc request of sending data to Mapper{mapper_port_id}")
            dump_master = open("./dump_master.txt", "a")
            dump_master.write(f"Sending grpc request of sending data to Mapper{mapper_port_id}\n")
            dump_master.close()
            response = stub.GetMapperData(request)
            dump_master = open("./dump_master.txt", "a")
            dump_master.write(f"Received grpc response from Mapper{mapper_port_id}\n")
            dump_master.close()
            print(f"Received grpc response from Mapper{mapper_port_id}")
            if response.status == "SUCCESS":
                print(f"Status of Mapper{response.mapper_id} Mapping Task: {response.status}")
                print(f"Status of Mapper{response.mapper_id} Partitioning Task: {response.status}")
                dump_master = open("./dump_master.txt", "a")
                dump_master.write(f"Status of Mapper{response.mapper_id} Mapping Task: {response.status}\n")
                dump_master.write(f"Status of Mapper{response.mapper_id} Partitioning Task: {response.status}\n")
                dump_master.close()
            else:
                dump_master = open("./dump_master.txt", "a")
                dump_master.write(f"Mapper{response.mapper_id} FAILED at {response.stage} stage. Retrying...\n")
                dump_master.close()
                print(f"Mapper{response.mapper_id} FAILED at {response.stage} stage. Retrying...")
                self.threadedSendMapperData(mapper_port_id)  # Restart thread for the same mapper_port_id
        except Exception as e:
            dump_master = open("./dump_master.txt", "a")
            dump_master.write(f"Mapper{mapper_port_id} Status: DOWN\n")
            dump_master.close()
            print(f"Mapper{mapper_port_id} Status: DOWN")
            print("Exception:", e)
            # If exception occurs, restart thread for the same mapper_port_id
            subprocess.Popen(["python3", "Mapper.py", "--mapperId", f"{mapper_port_id}", "--portNo", f"{self.mapper_ports[mapper_port_id]}", "--numReducers", f'{self.num_reducers}'])
            dump_master = open("./dump_master.txt", "a")
            dump_master.write(f"Mapper{mapper_port_id} Status: RESTARTED\n")
            dump_master.close()
            self.threadedSendMapperData(mapper_port_id)


    def startMapping(self):
        threads = []
        for mapper_port_id in range(len(self.mapper_ports)):
            thread = threading.Thread(target=self.threadedStartMapping, args=(mapper_port_id,))
            thread.start()
            threads.append(thread)

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

    def threadedStartMapping(self, mapper_port_id):
        channel = grpc.insecure_channel(self.ip+":"+str(self.mapper_ports[mapper_port_id]))
        stub = map_reduce_pb2_grpc.MapperServiceStub(channel)
        request = map_reduce_pb2.Empty()
        try:
            response = stub.Mapping(request)
            dump_master = open("./dump_master.txt", "a")
            dump_master.write(f"Status of Mapping of Mapper{response.mapper_id}: {response.status}\n")
            dump_master.close()
            print(f"Status of Mapping of Mapper{response.mapper_id}: {response.status}")
            if response.status != "SUCCESS":
                print(f"Mapper{response.mapper_id} FAILED. Retrying...")
                self.threadedStartMapping(mapper_port_id)
        except Exception as e:
            dump_master = open("./dump_master.txt", "a")
            dump_master.write(f"Status of Mapping of Mapper{self.mapper_port_id[self.mapper_ports[mapper_port_id]]}: FAILURE\n")
            dump_master.close()
            print(f"Status of Mapping of Mapper{self.mapper_port_id[self.mapper_ports[mapper_port_id]]}: FAILURE")
            print("Exception:", e)
            # If exception occurs, restart thread for the same mapper_port_id
            subprocess.Popen(["python3", "Mapper.py", "--mapperId", f"{mapper_port_id}", "--portNo", f"{self.mapper_ports[mapper_port_id]}", "--numReducers", f'{self.num_reducers}'])
            self.threadedSendMapperData(mapper_port_id)
            self.threadedStartMapping(mapper_port_id)
            
    def startPartitioning(self):
        threads = []
        for mapper_port_id in range(len(self.mapper_ports)):
            thread = threading.Thread(target=self.threadedStartPartitioning, args=(mapper_port_id,))
            thread.start()
            threads.append(thread)

        # Wait for all threads to complete
        for thread in threads:
            thread.join()
            
    def threadedStartPartitioning(self, mapper_port_id):
        channel = grpc.insecure_channel(self.ip+":"+str(self.mapper_ports[mapper_port_id]))
        stub = map_reduce_pb2_grpc.MapperServiceStub(channel)
        request = map_reduce_pb2.Empty()
        try:
            response = stub.Partitioning(request)
            dump_master = open("./dump_master.txt", "a")
            dump_master.write(f"Status of Partitioning of Mapper{response.mapper_id}: {response.status}\n")
            dump_master.close()
            print(f"Status of Partitioning of Mapper{response.mapper_id}: {response.status}")
            if response.status != "SUCCESS":
                print(f"Mapper{response.mapper_id} FAILED. Retrying...")
                self.threadedStartPartitioning(mapper_port_id)
        except Exception as e:
            dump_master = open("./dump_master.txt", "a")
            dump_master.write(f"Status of Partitioning of Mapper{self.mapper_port_id[self.mapper_ports[mapper_port_id]]}: FAILURE\n")
            dump_master.close()
            print(f"Status of Partitioning of Mapper{self.mapper_port_id[self.mapper_ports[mapper_port_id]]}: FAILURE")
            print("Exception:", e)
            # If exception occurs, restart thread for the same mapper_port_id
            subprocess.Popen(["python3", "Mapper.py", "--mapperId", f"{mapper_port_id}", "--portNo", f"{self.mapper_ports[mapper_port_id]}", "--numReducers", f'{self.num_reducers}'])
            self.threadedSendMapperData(mapper_port_id)
            self.threadedStartMapping(mapper_port_id)
            self.threadedStartPartitioning(mapper_port_id)

    def startReducers(self):
        threads = []
        for reducer_port_id in range(len(self.reducer_ports)):
            thread = threading.Thread(target=self.threadedStartReducers, args=(reducer_port_id,))
            thread.start()
            threads.append(thread)

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

    def threadedStartReducers(self, reducer_port_id):
        channel = grpc.insecure_channel(self.ip+":"+str(self.reducer_ports[reducer_port_id]))
        stub = map_reduce_pb2_grpc.ReducerServiceStub(channel)
        request = map_reduce_pb2.Empty()
        try:
            dump_master = open("./dump_master.txt", "a")
            dump_master.write(f"Sending grpc request to start Reducer{reducer_port_id}\n")
            dump_master.close()
            print(f"Sending grpc request to start Reducer{reducer_port_id}")
            response = stub.GetMapperData(request)
            dump_master = open("./dump_master.txt", "a")
            dump_master.write(f"Received grpc response from Reducer{reducer_port_id}\n")
            dump_master.close()
            print(f"Received grpc response from Reducer{reducer_port_id}")
            if response.status == "SUCCESS":
                print(f"Status of Reducer{response.reducer_id} Shuffle Sorting Task: {response.status}")
                print(f"Status of Reducer{response.reducer_id} Reducing Task: {response.status}")
                dump_master = open("./dump_master.txt", "a")
                dump_master.write(f"Status of Reducer{response.reducer_id} Mapping Task: {response.status}\n")
                dump_master.write(f"Status of Reducer{response.reducer_id} Partitioning Task: {response.status}\n")
                dump_master.close()
            else:
                dump_master = open("./dump_master.txt", "a")
                dump_master.write(f"Reducer{response.reducer_id} FAILED at {response.stage} stage. Retrying...\n")
                dump_master.close()
                print(f"Reducer{response.reducer_id} FAILED at {response.stage} stage. Retrying...")
                self.threadedStartReducers(reducer_port_id)  # Restart thread for the same mapper_port_id
        except Exception as e:
            dump_master = open("./dump_master.txt", "a")
            dump_master.write(f"Reducer{reducer_port_id} Status: DOWN\n")
            dump_master.close()
            print(f"Reducer{reducer_port_id} Status: DOWN")
            print("Exception:", e)
            # If exception occurs, restart thread for the same mapper_port_id
            subprocess.Popen(["python3", "Reducer.py", "--reducerId", f"{reducer_port_id}", "--portNo", f"{self.reducer_ports[reducer_port_id]}", "--mappers", f"{' '.join(str(x) for x in self.mapper_ports)}"])
            dump_master = open("./dump_master.txt", "a")
            dump_master.write(f"Reducer{reducer_port_id} Status: RESTARTED\n")
            dump_master.close()
            self.threadedStartReducers(reducer_port_id)

    def startShuffleSort(self):
        threads = []
        for reducer_port_id in range(len(self.reducer_ports)):
            thread = threading.Thread(target=self.threadedStartShuffleSorting, args=(reducer_port_id,))
            thread.start()
            threads.append(thread)

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

    def threadedStartShuffleSorting(self, reducer_port_id):
        channel = grpc.insecure_channel(self.ip+":"+str(self.reducer_ports[reducer_port_id]))
        stub = map_reduce_pb2_grpc.ReducerServiceStub(channel)
        request = map_reduce_pb2.Empty()
        try:
            response = stub.ShuffleSorting(request)
            dump_master = open("./dump_master.txt", "a")
            dump_master.write(f"Status of Shuffle Sort of Reducer{response.reducer_id}: {response.status}\n")
            dump_master.close()
            print(f"Status of Shuffle Sort of Reducer{response.reducer_id}: {response.status}")
            if response.status != "SUCCESS":
                print(f"Reducer{response.reducer_id} FAILED. Retrying...")
                self.threadedStartShuffleSorting(reducer_port_id)
        except Exception as e:
            dump_master = open("./dump_master.txt", "a")
            dump_master.write(f"Status of Shuffle Sort of Reducer{self.reducer_port_id[self.reducer_ports[reducer_port_id]]}: FAILURE\n")
            dump_master.close()
            print(f"Status of Shuffle Sort of Reducer{self.reducer_port_id[self.reducer_ports[reducer_port_id]]}: FAILURE")
            print("Exception:", e)
            # If exception occurs, restart thread for the same mapper_port_id
            subprocess.Popen(["python3", "Reducer.py", "--reducerId", f"{reducer_port_id}", "--portNo", f"{self.reducer_ports[reducer_port_id]}", "--mappers", f"{' '.join(str(x) for x in self.mapper_ports)}"])
            self.threadedStartReducers(reducer_port_id)
            self.threadedStartShuffleSorting(reducer_port_id)

    def startReducing(self):
        threads = []
        for reducer_port_id in range(len(self.reducer_ports)):
            thread = threading.Thread(target=self.threadedStartReducing, args=(reducer_port_id,))
            thread.start()
            threads.append(thread)

        # Wait for all threads to complete
        for thread in threads:
            thread.join()
            
    def threadedStartReducing(self, reducer_port_id):
        channel = grpc.insecure_channel(self.ip+":"+str(self.reducer_ports[reducer_port_id]))
        stub = map_reduce_pb2_grpc.ReducerServiceStub(channel)
        request = map_reduce_pb2.Empty()
        try:
            response = stub.Reducing(request)
            dump_master = open("./dump_master.txt", "a")
            dump_master.write(f"Status of Reduce of Reducer{response.reducer_id}: {response.status}\n")
            dump_master.close()
            print(f"Status of Reduce of Reducer{response.reducer_id}: {response.status}")
            if response.status != "SUCCESS":
                print(f"Reducer{response.reducer_id} FAILED. Retrying...")
                self.threadedStartReducing(reducer_port_id)
        except Exception as e:
            dump_master = open("./dump_master.txt", "a")
            dump_master.write(f"Status of Reduce of Reducer{self.reducer_port_id[self.reducer_ports[reducer_port_id]]}: FAILURE\n")
            dump_master.close()
            print(f"Status of Reduce of Reducer{self.reducer_port_id[self.reducer_ports[reducer_port_id]]}: FAILURE")
            print("Exception:", e)
            # If exception occurs, restart thread for the same mapper_port_id
            subprocess.Popen(["python3", "Reducer.py", "--reducerId", f"{reducer_port_id}", "--portNo", f"{self.reducer_ports[reducer_port_id]}", "--mappers", f"{' '.join(str(x) for x in self.mapper_ports)}"])
            self.threadedStartReducers(reducer_port_id)
            self.threadedStartShuffleSorting(reducer_port_id)
            self.threadedStartReducing(reducer_port_id)

    
    def getNewCentroids(self):
        self.converged = True
        threads = []
        self.pairs = []
        for reducer_port_id in range(len(self.reducer_ports)):
            thread = threading.Thread(target=self.threadedGetNewCentroids, args=(reducer_port_id,))
            thread.start()
            threads.append(thread)

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # print(self.centroids)
        centroids = open(f"./centroids.txt", "w")
        dump_master = open("./dump_master.txt", "a")
        dump_master.write("\nNew Centroids:\n")
        for pair in self.pairs:
            for pair_ in pair:
                print(round(pair_.value.x, 1), round(self.centroids[pair_.key].x, 1), round(pair_.value.y, 1), round(self.centroids[pair_.key].y, 1))
                if round(pair_.value.x, 1) != round(self.centroids[pair_.key].x, 1) and round(pair_.value.y, 1) != round(self.centroids[pair_.key].y, 1):
                    self.converged = False
                self.centroids[pair_.key] = pair_.value
        for centroid in self.centroids:
            centroids.write(f"{centroid.x}, {centroid.y}\n")
            dump_master.write(f"{centroid.x}, {centroid.y}\n")
        centroids.close()
        dump_master.close()
        return self.converged

    def threadedGetNewCentroids(self, reducer_port_id):
        channel = grpc.insecure_channel(self.ip+":"+str(self.reducer_ports[reducer_port_id]))
        stub = map_reduce_pb2_grpc.ReducerServiceStub(channel)
        request = map_reduce_pb2.CentroidRequest(portNo=str(self.portNo))
        try:
            response = stub.SendNewCentroids(request)
            if response.status == "SUCCESS":
                dump_master = open("./dump_master.txt", "a")
                dump_master.write(f"Status of Centroids Received from Reducer{reducer_port_id}: {response.status}\n")
                dump_master.close()
                print(f"Status of Centroids Received from Reducer{reducer_port_id}: {response.status}")
                key_values = response.key_value
                self.pairs.append(key_values)
            else:
                dump_master = open("./dump_master.txt", "a")
                dump_master.write(f"Status of Centroids Received from Reducer{reducer_port_id}: {response.status}\n")
                dump_master.close()
                print(f"Status of Centroids Received from Reducer{reducer_port_id}: {response.status}")
                self.threadedGetNewCentroids(reducer_port_id)
        except Exception as e:
                dump_master = open("./dump_master.txt", "a")
                dump_master.write(f"Status of Centroids Received from Reducer{reducer_port_id}: FAILURE\n")
                dump_master.close()
                print(f"Status of Centroids Received from Reducer{reducer_port_id}: FAILURE")
                print("Exception:", e)
                # If exception occurs, restart thread for the same mapper_port_id
                subprocess.Popen(["python3", "Reducer.py", "--reducerId", f"{reducer_port_id}", "--portNo", f"{self.reducer_ports[reducer_port_id]}", "--mappers", f"{' '.join(str(x) for x in self.mapper_ports)}"])
                self.threadedStartReducers(reducer_port_id)
                self.threadedStartShuffleSorting(reducer_port_id)
                self.threadedStartReducing(reducer_port_id)
                self.threadedGetNewCentroids(reducer_port_id)

if __name__=='__main__':
    print("Starting KMeans using Map-Reduce...")
    num_mappers = int(input("Enter number of Mappers: "))
    num_reducers = int(input("Enter number of Reducers: "))
    num_centroids = int(input("Enter number of Centroids: "))
    max_iters = int(input("Enter number of Iterations: "))

    open('./dump_master.txt', 'w').close()
    shutil.rmtree("./Mappers")
    shutil.rmtree("./Reducers")
    os.mkdir("./Mappers")
    os.mkdir("./Reducers")
    master = Master(num_mappers, num_reducers, num_centroids, max_iters, 50051, "./Input/points.txt")
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=20))
    # master.input_split("./Input/points.txt")
    map_reduce_pb2_grpc.add_MasterServiceServicer_to_server(master, server)
    print('Starting server. Listening on port 50051.')
    server.add_insecure_port('[::]:50051')
    server.start()
    print("Splitting Input Data...")
    master.input_split()
    print("Invoking Mappers...")
    master.invoke_mappers()
    print("Invoking Reducers...")
    master.invoke_reducers()
    time.sleep(5)
    
    for iteration in range(master.max_iterations):
        print("\nIteration Number:", iteration+1)
        dump_master = open("./dump_master.txt", "a")
        dump_master.write(f"\nIteration {iteration+1}\n")
        dump_master.close()
        print("\nCentroids for this Iteration:")
        print(master.centroids)
        print("\nSending Data to Mappers...")
        master.sendMapperData()
        # print("\nStart Mapping...")
        # master.startMapping()
        # print("\nStart Partitioning...")
        # master.startPartitioning()

        print("\nStart Reducers to Get Data from Mappers...")
        master.startReducers()
        # print("\nStart Shuffle Sorting...")
        # master.startShuffleSort()
        # print("\nStart Reducing...")
        # master.startReducing()
        print("\nGetting New Centroids...")
        converged = master.getNewCentroids()
        print()
        if converged:
            print("Converged before Maximum Iterations")
            break
    print("KMeans Finished.")
    server.wait_for_termination()

