import grpc
from concurrent import futures
import map_reduce_pb2
import map_reduce_pb2_grpc
import argparse
import socket
import math
import os
import shutil
from random import choices
import time

class Mapper(map_reduce_pb2_grpc.MapperServiceServicer):
    def __init__(self, mapperId, portNo, numReducers):
        self.mapperId = mapperId
        self.indices = None
        self.centroids = None
        self.portNo = portNo
        self.numReducers = numReducers
        if os.path.exists(f"./Mappers/M{self.mapperId}"):
            # os.rmdir(f"./Mappers/M{portNo-50051}")
            shutil.rmtree(f"./Mappers/M{self.mapperId}")
        os.mkdir(f"./Mappers/M{self.mapperId}")
        self.ip = socket.gethostbyname(socket.gethostname())
        self.input_path = ""
        self.input = []
        self.partitions = []
        self.mapper_output = []

    def get_distance(self, point1, point2):
        return math.sqrt(math.pow(point1.x - point2.x, 2) + math.pow(point1.y-point2.y, 2))

    def GetMapperData(self, request, context):
        flag = choices([0,1], [0.2, 0.8])[0]
        time.sleep(5)
        if flag == 1:
            self.indices = request.input_split
            self.centroids = request.centroids
            self.input_path = request.input_path
            dump_mapper = open(f"./Mappers/M{self.mapperId}/dump_mapper_M{self.mapperId}.txt", "a")
            dump_mapper.write(f"\nMapper{self.mapperId} Status of Data Received: SUCCESS")
            dump_mapper.close()
            map_status = self.Map(self.indices, self.centroids)
            dump_mapper = open(f"./Mappers/M{self.mapperId}/dump_mapper_M{self.mapperId}.txt", "a")
            dump_mapper.write(f"\nMapper{self.mapperId} Status of Mapping: {map_status}")
            dump_mapper.close()
            if map_status == "FAILURE":
                return map_reduce_pb2.MapDataResponse(mapper_id=self.mapperId, stage="Mapping", status="FAILURE")
            part_status = self.Partition(self.mapper_output)
            dump_mapper = open(f"./Mappers/M{self.mapperId}/dump_mapper_M{self.mapperId}.txt", "a")
            dump_mapper.write(f"\nMapper{self.mapperId} Status of Partitioning: {part_status}")
            dump_mapper.close()
            if part_status == "FAILURE":
                return map_reduce_pb2.MapDataResponse(mapper_id=self.mapperId, stage="Partitioning", status="FAILURE")
            return map_reduce_pb2.MapDataResponse(mapper_id=self.mapperId, stage="All", status="SUCCESS")
        dump_mapper = open(f"./Mappers/M{self.mapperId}/dump_mapper_M{self.mapperId}.txt", "a")
        dump_mapper.write(f"\nMapper{self.mapperId} Status of Data Received: FAILURE")
        dump_mapper.close()
        return map_reduce_pb2.MapDataResponse(mapper_id=self.mapperId, stage="Data Sending", status="FAILURE")

    def Heartbeat(self, request, context):
        return map_reduce_pb2.MapDataResponse(mapper_id=self.mapperId, status="SUCCESS")
    
    def Mapping(self, request, context):
        flag = choices([0,1], [0.2, 0.8])[0]
        time.sleep(5)
        if flag == 1:
            self.Map(self.indices, self.centroids)
            return map_reduce_pb2.MapDataResponse(mapper_id=self.mapperId, status="SUCCESS")
        return map_reduce_pb2.MapDataResponse(mapper_id=self.mapperId, status="FAILURE")
    
    def Partitioning(self, request, context):
        flag = choices([0,1], [0.2, 0.8])[0]
        time.sleep(5)
        if flag == 1:
            self.Partition(self.mapper_output)
            return map_reduce_pb2.MapDataResponse(mapper_id=self.mapperId, status="SUCCESS")
        return map_reduce_pb2.MapDataResponse(mapper_id=self.mapperId, status="FAILURE")

    def GetDataFromMaster(self):
        channel = grpc.insecure_channel(self.ip+":50051")
        stub = map_reduce_pb2_grpc.MasterServiceStub(channel)
        request = map_reduce_pb2.MapDataRequest(ip="[::]:"+str(self.portNo), mapper_id=self.mapperId)
        response = stub.SendMapperData(request)
        self.indices = response.input_split
        self.centroids = response.centroids
        self.input_path = response.input_path
        self.Map(self.indices, self.centroids)

    def SendKeyValuePair(self, request, context):
        flag = choices([0,1], [0.2, 0.8])[0]
        reducerId = request.reducerId
        if flag == 1:
            partition = self.partitions[reducerId].copy()
            for i in range(len(partition)):
                partition[i] = map_reduce_pb2.KeyValue(key=partition[i][0], value=partition[i][1])
            return map_reduce_pb2.KeyValueResponse(key_value_pairs=partition, status="SUCCESS")
        dump_mapper = open(f"./Mappers/M{self.mapperId}/dump_mapper_M{self.mapperId}.txt", "a")
        dump_mapper.write(f"\nSending grpc Response to Reducer{reducerId}")
        dump_mapper.close()
        dump_mapper = open(f"./Mappers/M{self.mapperId}/dump_mapper_M{self.mapperId}.txt", "a")
        dump_mapper.write(f"\nStatus of Mapper{self.mapperId} sending data: FAILURE")
        dump_mapper.close()
        return map_reduce_pb2.KeyValueResponse(status="FAILURE")
        

    def Map(self, indices, centroids):
        flag = choices([0,1], [0.2, 0.8])[0]
        time.sleep(5)
        if flag == 1:
            file = open(self.input_path, "r")
            data_points = file.read().split("\n")
            data_points = [map_reduce_pb2.Point(x=float(data_points[i].split(",")[0]), y=float(data_points[i].split(",")[1])) for i in indices]
            # print(data_points)
            file.close()
            mapper_output = []
            self.input = data_points
            dump_mapper = open(f"./Mappers/M{self.mapperId}/dump_mapper_M{self.mapperId}.txt", "a")
            dump_mapper.write(f"\nMap Output for Mapper{self.mapperId}\n")
            for point in self.input:
                min_dist = math.inf
                min_centroid = 0
                for i in range(len(centroids)):
                    if min_dist > self.get_distance(point, centroids[i]):
                        min_centroid = i
                        min_dist = self.get_distance(point, centroids[i])
                mapper_output.append((min_centroid, point))
                dump_mapper.write(f'({min_centroid}, {(point.x, point.y)})\n')
            self.mapper_output = mapper_output
            dump_mapper.close()
            return "SUCCESS"
        # self.Partition(mapper_output)
        return "FAILURE"

    def Partition(self, mapper_output):
        flag = choices([0,1], [0.2, 0.8])[0]
        time.sleep(5)
        if flag == 1:
            partitions = []
            for i in range(self.numReducers):
                partition = open(f"./Mappers/M{self.mapperId}/partition_{i+1}.txt", "w")
                partitions.append([])
                partition.close()
                
            for key, value in mapper_output:
                # Use a hash function to determine the reducer for this key
                reducer_id = key % self.numReducers
                partition = open(f"./Mappers/M{self.mapperId}/partition_{reducer_id+1}.txt", "a")
                partition.write(f'({key}, {(value.x, value.y)})\n')
                partition.close()
                partitions[reducer_id].append((key, value))
            self.partitions = partitions

            dump_mapper = open(f"./Mappers/M{self.mapperId}/dump_mapper_M{self.mapperId}.txt", "a")
            dump_mapper.write(f"\nPartition Output for Mapper{self.mapperId}")
            for i in range(len(partitions)):
                dump_mapper.write(f'\nPartition {i+1}\n')
                for key, value in partitions[i]:
                    dump_mapper.write(f'({key}, {(value.x, value.y)})\n')
            dump_mapper.close()
            return "SUCCESS"
        return "FAILURE"


if __name__=='__main__':
    argparser = argparse.ArgumentParser()
    argparser.add_argument("--mapperId", type=int)
    argparser.add_argument("--portNo", type=int)
    argparser.add_argument("--numReducers", type=int)
    
    mapperId = argparser.parse_args().mapperId
    portNo = argparser.parse_args().portNo
    numReducers = argparser.parse_args().numReducers
    
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    mapper = Mapper(mapperId, portNo, numReducers)
    map_reduce_pb2_grpc.add_MapperServiceServicer_to_server(mapper, server)
    open(f"./Mappers/M{mapperId}/dump_mapper_M{mapperId}.txt", 'w').close()
    server.add_insecure_port("[::]:"+str(portNo))
    server.start()
    # mapper.GetDataFromMaster()
    server.wait_for_termination()