import threading
import time
import random
import zmq
import math
import os
from zmq.utils.monitor import recv_monitor_message
from typing import Dict, Any
import argparse
import json
import grpc
from concurrent import futures 
import node_pb2
import node_pb2_grpc

class MyTimer:
    def __init__(self, interval, onEndCallback) -> None:
        self.interval = interval
        self.onEndCallback = onEndCallback
    
    def start(self, ):
        self.start_time = time.time()
        self._timer = threading.Timer(self.interval, self.onEndCallback if self.onEndCallback is not None else lambda: None)
        self._timer.start()

    def remaining(self):
        return self.start_time + self._timer.interval - time.time()
    
    def cancel(self):
        self._timer.cancel()

    def elapsed(self):
        return time.time() - self.start_time

EVENT_MAP = {}
# print("Event names:")
for name in dir(zmq):
    if name.startswith('EVENT_'):
        value = getattr(zmq, name)
        # print("%21s : %4i" % (name, value))
        EVENT_MAP[value] = name

def event_monitor(monitor: zmq.Socket,node_id,follower_id) -> None:
    while monitor.poll():
        evt: Dict[str, Any] = {}
        mon_evt = recv_monitor_message(monitor)
        evt.update(mon_evt)
        evt['description'] = EVENT_MAP[evt['event']]
        # print(f"Event: {evt}") 
        if evt['event'] == zmq.EVENT_CONNECT_RETRIED:
            # print("Connection to Node "+str(id)+" failed. Retrying...")
            with open("logs_node_"+str(node_id)+"/dump.txt", "a", newline="") as file:
                file.write("Error occurred while sending RPC to Node "+str(follower_id)+"\n")
            print("Error occurred while sending RPC to Node "+str(follower_id))
            break
    monitor.close()
    print()
    # print("event monitor thread done!")

class RaftNode(node_pb2_grpc.NodeServicer):
    def __init__(self, node_id, restarting=False):
        """
        From Pseudocode 1/9
        """
        self.node_id = node_id
        self.current_term = 0
        self.voted_for = None
        self.log = []
        self.data_truths = {}
        self.commit_length = 0
        self.current_role = "Follower"
        self.current_leader = None
        self.votes_received = set()
        self.sent_length = {}
        self.acked_length = {}

        # Read connections_grpc.json
        with open('connections_grpc.json') as f:
            self.connections = json.load(f)

        self_addr = self.connections[str(node_id)]

        # self_addr = self_addr.replace("localhost", "*")

        self.self_addr = self_addr

        del self.connections[str(node_id)]

        for key in self.connections:
            self.sent_length[key] = 0
            self.acked_length[key] = 0

        # self.global_zmq_socket = zmq.Context().socket(zmq.PULL)
        # self.global_zmq_socket.bind(self_addr)

        # Connection to Nodes needs to be there somehow, let's assume it's a list of addresses
        # self.connections = {'1': "tcp://localhost:5556", '2': "tcp://localhost:5557", '3': "tcp://localhost:5558", '4': "tcp://localhost:5559", '5': "tcp://localhost:5560"}
        # self.connections = {int(k): v for k, v in self.connections.items()}
        # {1: IP, 2: IP}

        # self.log_file =  open("logs_node_0/logs.txt", "w")
        # TODO change the reconntruction of log file
        if restarting == False:
            if os.path.isfile("logs_node_"+str(node_id)+"/logs.txt"):
                os.remove("logs_node_"+str(node_id)+"/logs.txt")
            if os.path.isfile("logs_node_"+str(node_id)+"/metadata.txt"):
                os.remove("logs_node_"+str(node_id)+"/metadata.txt")
            if os.path.isfile("logs_node_"+str(node_id)+"/dump.txt"):
                os.remove("logs_node_"+str(node_id)+"/dump.txt")
        else:
            self.restarting_node()

        self.MAX_LEASE_TIMER_LEFT = 7
        self.HEARTBEAT_TIMEOUT = 1
        self.COUNT_OF_SUCCESSFUL_LEASE_RENEWALS = 0

        self.handle_timers()

    def restarting_node(self):
        self.recovery_from_crash()
        # Read metadata.txt
        with open("logs_node_"+str(self.node_id)+"/metadata.txt", "r") as file:
            metadata = file.read().split(" ")
            self.commit_length = int(metadata[2])
            self.current_term = int(metadata[4])
            self.voted_for = int(metadata[-1])
        # Read logs.txt
        with open("logs_node_"+str(self.node_id)+"/logs.txt", "r") as file:
            logs = file.readlines()
            for idx, log in enumerate(logs):
                term, message = log.split(" ")
                self.log.append({"term": term, "message": message})
                if idx <= self.commit_length:
                    if message.startswith("SET"):
                        _, key, value = message.split(" ")
                        self.data_truths[key] = value

    def recovery_from_crash(self):
        """
        From Pseudocode 1/9
        """
        self.current_role = "Follower"
        self.votes_received = set()
        self.sent_length = {}
        self.acked_length = {}
        for key in self.connections:
            self.sent_length[key] = 0
            self.acked_length[key] = 0
        self.current_leader = None

    def handle_timers(self, converting_to_leader=False, term=None):
        print("handle timers called", self.current_role)
        if self.current_role == 'Leader':
            self.timer = MyTimer(self.HEARTBEAT_TIMEOUT, self.periodic_heartbeat)
            self.timer.start()
            self.lease_timer = MyTimer(self.MAX_LEASE_TIMER_LEFT, self.step_down)
            self.lease_timer.start()
        elif self.current_role != 'Leader' and not converting_to_leader:
            MIN_TIMEOUT = 5
            MAX_TIMEOUT = 10
            self.timer = MyTimer(random.randint(MIN_TIMEOUT, MAX_TIMEOUT), self.leader_failed_or_election_timeout)
            self.timer.start()
            self.lease_timer = MyTimer(self.MAX_LEASE_TIMER_LEFT, None)
            self.lease_timer.start()
        elif self.current_role == 'Candidate' and converting_to_leader and self.current_leader != None:
            self.lease_timer = MyTimer(self.MAX_LEASE_TIMER_LEFT, self.convert_to_leader_on_lease_timer_end)
            self.lease_timer.start()
            with open("logs_node_"+str(self.node_id)+"/dump.txt", "a", newline="") as file:
                file.write("Node "+str(self.node_id)+" waiting for old lease to expire \n")
            print("Node "+str(self.node_id)+" waiting for old lease to expire ")

    def convert_to_leader_on_lease_timer_end(self):
        self.current_role = "Leader"
        self.current_leader = self.node_id
        with open("logs_node_"+str(self.node_id)+"/dump.txt", "a", newline="") as file:
            file.write("Node "+str(self.node_id)+" became the leader for term "+str(self.term)+"\n")
        print("Node "+str(self.node_id)+" became the leader for term "+str(self.term))
        self.cancel_timers()
        self.handle_timers()

    def cancel_timers(self):
        if hasattr(self, 'timer'):
            self.timer.cancel()
        if hasattr(self, 'lease_timer'):
            self.lease_timer.cancel()

    def step_down(self):
        if self.current_role == "Leader":
            with open("logs_node_"+str(self.node_id)+"/dump.txt", "a", newline="") as file:
                file.write("Leader "+str(self.node_id)+" lease timer timed out. Stepping down. \n")
            print("Leader "+str(self.node_id)+" lease timer timed out. Stepping down.")
            self.current_role = "Follower"
            self.voted_for = None
            self.cancel_timers()
            self.handle_timers()

    def main(self,request, context):
        iteration = 0
    
        # print("Iteration: ", iteration)
        try:
            message = request.message
        except Exception as e:
            print("Exception: ", e)
            # self.global_zmq_socket = zmq.Context().socket(zmq.REP)
            # self.global_zmq_socket.bind(self.self_addr)  
        print("Received message: ", message , " at " , time.time())
        message_parts = message.split(" ")
        if message_parts[0] == "VoteRequest":
            cId, cTerm, cLogLength, cLogTerm = message_parts[1:]
            self.handle_vote_request(int(cId), int(cTerm), int(cLogLength), int(cLogTerm))
        elif message_parts[0] == "VoteResponse":
            voterId, term, granted, lease_timer_left_according_to_voter = message_parts[1:]
            self.handle_vote_response(int(voterId), int(term), granted == "True", float(lease_timer_left_according_to_voter))
        elif message_parts[0] == "LogRequest":
            # print(message_parts)
            # print("Length of message parts: ", len(message_parts))
            leader_id, term, prefix_len, prefix_term, leader_commit = message_parts[1:6]
            lease_timer_left_according_to_leader = message_parts[-1]
            suffix = message_parts[6:-1]
            suffix = " ".join(suffix)
            # print(suffix)
            suffix = eval(suffix)
            # print("Suffix: ", suffix)
            lease_timer_left_according_to_leader = float(lease_timer_left_according_to_leader)
            self.handle_log_request(int(leader_id), int(term), int(prefix_len), int(prefix_term), int(leader_commit), suffix, lease_timer_left_according_to_leader)
        elif message_parts[0] == "LogResponse":
            follower_id, term, ack, success = message_parts[1:]
            self.handle_log_response(int(follower_id), int(term), int(ack), success == "True")
        # elif message_parts[0] == "AppendEntries":
        #     prefix_len, leader_commit, suffix = message_parts[1:]
        #     self.append_entries(int(message_parts[1]), int(message_parts[2]), message_parts[3])
        elif message_parts[0] == "Forward":
            node_id, current_term, message = message_parts[1:]
            self.broadcast_messages(message)
        elif message_parts[0] == "GET":
            # TODO: Need to change get_query to return only if reader
            key = message_parts[1]
            return_address = message_parts[2]
            status, returnVal = self.get_query(key)
            # print("Get Query: ", status, returnVal)
            # Return the value to the return address
            # TODO : Check if client is active or not
            client_socket = zmq.Context().socket(zmq.PUSH)
            client_socket.connect(return_address)
            return_msg = str(status) + " " + str(returnVal)
            encoded_msg = return_msg.encode()
            client_socket.send(encoded_msg)
        elif message_parts[0] == "SET":
            # TODO  
            key, value,return_address = message_parts[1:]
            self.set_query(key, value,return_address)
        iteration += 1
        return node_pb2.res()
    

    def get_query(self, key):
        if self.current_role == "Leader":
            # print("Leader Get")
            # print(self.data_truths)
            # print(self.log)
            # print(self.commit_length)
            if key in self.data_truths:
                return 1, self.data_truths[key]
            else:
                return 2, ""
        else:
            if self.current_leader is None:
                return 0, "None"
            else:
                return 0, self.current_leader
        
    def set_query(self, key, value,return_address):
        if self.current_role == "Leader":
            # don't we need to send some success or failure message to the client
            status = "1"
            client_socket = zmq.Context().socket(zmq.PUSH)
            client_socket.connect(return_address)
            client_socket.send(f"{status}".encode())
            self.broadcast_messages("SET " + key + " " + value)
        else:
            status = "0"
            returnVal = self.current_leader
            client_socket = zmq.Context().socket(zmq.PUSH)
            client_socket.connect(return_address)
            client_socket.send(f"{status} {returnVal}".encode())
            # return self.current_leader


    def leader_failed_or_election_timeout(self):
        """
        From Pseudocode 1/9
        """
        self.cancel_timers()
        with open("logs_node_"+str(self.node_id)+"/dump.txt", "a", newline="") as file:
            file.write("Node "+str(self.node_id)+" election timer timed out, Starting election. \n")

        print("Node "+str(self.node_id)+" election timer timed out, Starting election. ")
        self.current_term += 1
        self.current_role = "Candidate"
        self.voted_for = self.node_id
        self.votes_received = {self.node_id}
        last_term = 0
        if len(self.log) > 0:
            last_term = self.log[-1]["term"]
        message = "VoteRequest " + str(self.node_id) + " " + str(self.current_term) + " " + str(len(self.log)) + " " + str(last_term)
        for n_id, connection in self.connections.items():
            # print("Sending Vote Request to Node "+str(n_id))
            # context = zmq.Context()
            # # print("Context Created")
            # socket = context.socket(zmq.PUSH)
            # # print("Socket Created")
            # monitor = socket.get_monitor_socket()
            # # print("Monitor Created")
            # t = threading.Thread(target=event_monitor, args=(monitor,self.node_id,n_id))
            # # print("Thread Created")
            # t.start()
            # # print("Thread Started")
            # socket.connect(connection)
            # # print("Connected")
            # socket.send(message.encode())
            # print("Message Sent")
            # response = socket.recv().decode()
            # reply_type, voterId, voter_term, granted = response.split(" ")
            # if granted == "True":
            #     self.handle_vote_response(voterId, voter_term, granted)
            channel = grpc.insecure_channel(connection)
            stub = node_pb2_grpc.NodeStub(channel)
            request = node_pb2.req(message= message)
            try:
                stub.main(request)
            except Exception as e:
                print(e)
                print("Error occurred while sending RPC to Node "+str(n_id))
                with open("logs_node_"+str(self.node_id)+"/dump.txt", "a", newline="") as file:
                    file.write("Error occurred while sending RPC to Node "+str(n_id)+"\n")

        self.handle_timers()

    def handle_vote_request(self, cId, cTerm, cLogLength, cLogTerm):
        """
        From Pseudocode 2/9
        """
        self.cancel_timers()
        if cTerm > self.current_term:
            self.current_role = "Follower"
            self.current_term = cTerm
            self.voted_for = None
        last_term = 0
        if len(self.log) > 0:
            last_term = self.log[-1]["term"]
        logOk = (cLogTerm > last_term) or (cLogTerm == last_term and cLogLength >= len(self.log))
        if cTerm == self.current_term and logOk and (self.voted_for is None or self.voted_for == cId):
            self.voted_for = cId
            time_left_in_leader_lease = self.lease_timer.remaining()
            message = "VoteResponse " + str(self.node_id) + " " + str(self.current_term) + " " + str(True)  + " " + str(time_left_in_leader_lease)
            candidate_socket_addr = self.connections[str(cId)]
            # context = zmq.Context()
            # candidate_socket = context.socket(zmq.PUSH)
            # monitor = candidate_socket.get_monitor_socket()
            # # print("Monitor Created")
            # t = threading.Thread(target=event_monitor, args=(monitor,self.node_id,cId))
            # # print("Thread Created")
            # t.start()
            # candidate_socket.connect(candidate_socket_addr)
            # candidate_socket.send(message.encode())
            channel = grpc.insecure_channel(candidate_socket_addr)
            stub = node_pb2_grpc.NodeStub(channel)
            request = node_pb2.req(message= message)
            try:
                stub.main(request)
                with open("logs_node_"+str(self.node_id)+"/dump.txt", "a", newline="") as file:
                    file.write("Vote Granted for Node "+str(cId)+" in term."+str(cTerm) +"\n")
                print("Vote Granted for Node "+str(cId)+" in term."+str(cTerm))
            except Exception as e:
                print(e)
                print("Error occurred while sending RPC to Node "+str(cId))
                with open("logs_node_"+str(self.node_id)+"/dump.txt", "a", newline="") as file:
                    file.write("Error occurred while sending RPC to Node "+str(cId)+"\n")

            # Even if the one you vote for doesn't wins, you'll recieve heartbeat so no need to handle response 
            # response = self.global_zmq_socket.recv().decode()
            # # Handle response
        else:
            # Reply no vote
            time_left_in_leader_lease = self.lease_timer.remaining()
            message = "VoteResponse " + str(self.node_id) + " " + str(self.current_term) + " " + str(False) + " " + str(time_left_in_leader_lease)
            candidate_socket_addr = self.connections[str(cId)]
            # context = zmq.Context()
            # candidate_socket = context.socket(zmq.PUSH)
            # monitor = candidate_socket.get_monitor_socket()
            # # print("Monitor Created")
            # t = threading.Thread(target=event_monitor, args=(monitor,self.node_id,cId))
            # # print("Thread Created")
            # t.start()
            # candidate_socket.connect(candidate_socket_addr)
            # candidate_socket.send(message.encode())
            channel = grpc.insecure_channel(candidate_socket_addr)
            stub = node_pb2_grpc.NodeStub(channel)
            request = node_pb2.req(message= message)
            try:
                stub.main(request)
                with open("logs_node_"+str(self.node_id)+"/dump.txt", "a", newline="") as file:
                    file.write("Vote denied for Node "+str(cId)+" in term."+str(cTerm) +"\n")
                print("Vote denied for Node "+str(cId)+" in term."+str(cTerm))
            except Exception as e:
                print(e)
                print("Error occurred while sending RPC to Node "+str(cId))
                with open("logs_node_"+str(self.node_id)+"/dump.txt", "a", newline="") as file:
                    file.write("Error occurred while sending RPC to Node "+str(cId)+"\n")
            # response = self.global_zmq_socket.recv().decode()
            # # Handle response
        self.handle_timers()
    
    def handle_vote_response(self, voterId, term, granted, lease_timer_left_according_to_voter):
        """
        From Pseudocode 3/9
        """
        self.MAX_LEASE_TIMER_LEFT = max(self.MAX_LEASE_TIMER_LEFT, lease_timer_left_according_to_voter)
        if self.current_role == 'Candidate' and term == self.current_term and granted:
            self.votes_received.add(voterId)
            if len(self.votes_received) >= math.ceil((len(self.connections) + 1) / 2):
                self.current_role = "Leader"
                with open("logs_node_"+str(self.node_id)+"/dump.txt", "a", newline="") as file:
                    file.write("Node "+str(self.node_id)+" became the leader for term "+str(term)+"\n")
                print("Node "+str(self.node_id)+" became the leader for term "+str(term))
                self.current_leader = self.node_id
                # Cancel election timer
                self.cancel_timers()
                # self.handle_timers(converting_to_leader=True)
                self.handle_timers()
                # Send AppendEntries to all other nodes
                # TODO: Check if this is correct

                with open("logs_node_"+str(self.node_id)+"/logs.txt", "a", newline="") as file:
                    file.write("No-OP "+str(self.current_term) +"\n")
                print("No-OP "+str(self.current_term) )
                self.log.append({"term": self.current_term, "message": "No-OP"})
                # when it will be restarted it will reload logs

                for follower, _ in self.connections.items():
                    self.sent_length[follower] = len(self.log)
                    self.acked_length[follower] = 0
                    self.replicate_log(self.node_id, follower)
        elif term > self.current_term:
            self.current_role = "Follower"
            self.current_term = term
            self.voted_for = None
            self.cancel_timers()
            self.handle_timers()

    def broadcast_messages(self, message):
        """
        From Pseudocode 4/9
        """
        if self.current_role == "Leader":
            self.log.append({"term": self.current_term, "message": message})
            with open("logs_node_"+str(self.node_id)+"/dump.txt", "a", newline="") as file:
                file.write("Leader Node "+str(self.node_id)+" received an entry request "+message+"\n")
            print("Leader Node "+str(self.node_id)+" received an entry request "+message+"\n")
            self.acked_length[self.node_id] = len(self.log)
            self.COUNT_OF_SUCCESSFUL_LEASE_RENEWALS = 0
            for follower, _ in self.connections.items():
                self.replicate_log(self.node_id, follower)
        else:
            # Forward to Leader
            # context = zmq.Context()
            # socket = context.socket(zmq.PUSH)
            # socket.connect(self.connections[self.current_leader])
            # monitor = socket.get_monitor_socket()
            # t = threading.Thread(target=event_monitor, args=(monitor,1,0))
            # t.start()

            message = "Forward " + str(self.node_id) + " " + str(self.current_term) + " " + message
            channel = grpc.insecure_channel(self.connections[self.current_leader])
            stub = node_pb2_grpc.NodeStub(channel)
            request = node_pb2.req(message= message)
            # socket.send(message.encode())
            try:
                stub.main(request)
            # response = self.global_zmq_socket.recv().decode()
            except Exception as e:
                print(e)
                print("Error occurred while sending RPC to Node "+str(self.current_leader))
                with open("logs_node_"+str(self.node_id)+"/dump.txt", "a", newline="") as file:
                    file.write("Error occurred while sending RPC to Node "+str(self.current_leader)+"\n")

    def periodic_heartbeat(self):
        """
        From Pseudocode 4/9
        """
        if self.current_role == "Leader":
            # TODO = "Leader {NodeID of Leader} lease renewal failed. Stepping Down."
            with open("logs_node_"+str(self.node_id)+"/dump.txt", "a", newline="") as file:
                file.write("Leader "+str(self.node_id)+" sending heartbeat & Renewing Lease \n")
            print("Leader "+str(self.node_id)+" sending heartbeat & Renewing Lease ")
            self.COUNT_OF_SUCCESSFUL_LEASE_RENEWALS = 0
            # self.cancel_timers()
            # self.handle_timers()
            for follower, _ in self.connections.items():
                self.replicate_log(self.node_id, follower)

    def replicate_log(self, leader_id, follower_id):
        """
        From Pseudocode 5/9
        """
        # Cancelling and restarting the timers otherwise the leader keeps getting timed out
        # print("Replicating log from Leader "+str(leader_id)+" to Follower "+str(follower_id))
        prefix_len = self.sent_length[follower_id]
        # print("Leader Debug", self.log, prefix_len, self.sent_length, self.acked_length, self.commit_length)
        # [1,2,3,4,5]
        suffix = self.log[prefix_len:]
        prefix_term = 0
        if prefix_len > 0:
            prefix_term = self.log[prefix_len - 1]["term"]
        lease_timer_left = self.lease_timer.remaining()
        message = "LogRequest " + str(leader_id) + " " + str(self.current_term) + " " + str(prefix_len) + " " + str(prefix_term) + " " + str(self.commit_length) + " " + str(suffix) + " " + str(lease_timer_left)
        # print("Replicate Log Message: ", message)
        # context = zmq.Context()
        # socket = context.socket(zmq.PUSH)
        # monitor = socket.get_monitor_socket()
        # t = threading.Thread(target=event_monitor, args=(monitor,self.node_id,follower_id))
        # t.start()
        # socket.connect(self.connections[follower_id])
        # socket.send(message.encode())
        channel = grpc.insecure_channel(self.connections[follower_id])
        stub = node_pb2_grpc.NodeStub(channel)
        request = node_pb2.req(message= message)
        try:
            stub.main(request)
            print("Replicated log from Leader "+str(leader_id)+" to Follower "+str(follower_id))
        except Exception as e:
            print(e)
            print("Error occurred while sending RPC to Node "+str(follower_id))
            with open("logs_node_"+str(self.node_id)+"/dump.txt", "a", newline="") as file:
                file.write("Error occurred while sending RPC to Node "+str(follower_id)+"\n")

    def handle_log_request(self, leader_id, term, prefix_len, prefix_term, leader_commit, suffix, lease_timer_left_according_to_leader):
        """
        From Pseudocode 6/9
        """
        if self.current_role != "Leader":
            self.cancel_timers()
            self.handle_timers()
        self.MAX_LEASE_TIMER_LEFT = max(self.MAX_LEASE_TIMER_LEFT, lease_timer_left_according_to_leader)
        if term > self.current_term:
            self.current_term = term
            self.voted_for = None
            self.cancel_timers()
            self.handle_timers()
        if term == self.current_term:
            self.current_role = "Follower"
            self.current_leader = leader_id
            # TODO: Check if this is correct adding the timer
            self.cancel_timers()
            self.handle_timers()
        # print(self.log, prefix_len)
        # print("DEBUG", self.log, prefix_len, prefix_term, term, self.current_term, leader_commit, suffix, self.sent_length)
        logOk = len(self.log) >= prefix_len and (prefix_len == 0 or self.log[prefix_len-1]["term"] == prefix_term)
        if term == self.current_term and logOk:
            self.append_entries(prefix_len, leader_commit, suffix)
            ack = prefix_len + len(suffix)
            log_response_message = "LogResponse " + str(self.node_id) + " " + str(self.current_term) + " " + str(ack) + " " + str(True)
        else:
            # print("Rejected Append E")
            with open("logs_node_"+str(self.node_id)+"/dump.txt", "a", newline="") as file:
                    file.write("Node "+str(self.node_id)+"  rejected AppendEntries RPC from "+str(self.current_leader)+ "\n")
            print("Node "+str(self.node_id)+"  rejected AppendEntries RPC from "+str(self.current_leader))
            log_response_message = "LogResponse " + str(self.node_id) + " " + str(self.current_term) + " " + "0" + " " + str(False)
        candidate_socket_addr = self.connections[str(leader_id)]
        # context = zmq.Context()
        # candidate_socket = context.socket(zmq.PUSH)
        # monitor = candidate_socket.get_monitor_socket()
        # # print("Monitor Created")
        # t = threading.Thread(target=event_monitor, args=(monitor,self.node_id,leader_id))
        # # print("Thread Created")
        # t.start()
        # candidate_socket.connect(candidate_socket_addr)
        # candidate_socket.send(log_response_message.encode())
        channel = grpc.insecure_channel(candidate_socket_addr)
        stub = node_pb2_grpc.NodeStub(channel)
        request = node_pb2.req(message= log_response_message)
        try:
            stub.main(request)
        # response = self.global_zmq_socket.recv().decode()
        except Exception as e:
            print(e)
            print("Error occurred while sending RPC to Node "+str(leader_id))
            with open("logs_node_"+str(self.node_id)+"/dump.txt", "a", newline="") as file:
                file.write("Error occurred while sending RPC to Node "+str(leader_id)+"\n")



    def append_entries(self, prefix_len, leader_commit, suffix):
        """
        From Pseudocode 7/9
        """
        if len(suffix) > 0 and len(self.log) > prefix_len:
            index = min(len(self.log), prefix_len + len(suffix)) - 1
            if self.log[index]["term"] != suffix[index - prefix_len]["term"]:
                self.log = self.log[:prefix_len]
        
        if prefix_len + len(suffix) > len(self.log):
            for i in range(len(self.log) - prefix_len, len(suffix)):
                self.log.append(suffix[i])
                with open("logs_node_"+str(self.node_id)+"/dump.txt", "a", newline="") as file:
                    file.write("Node "+str(self.node_id)+"  accepted AppendEntries RPC from "+str(self.current_leader)+ "\n")
                print("Node "+str(self.node_id)+"  accepted AppendEntries RPC from "+str(self.current_leader))
                # TODO: check if writing to log is correct
                last_message = suffix[i]["message"]   
                with open("logs_node_"+str(self.node_id)+"/logs.txt", "a", newline="") as file:
                    file.write(last_message +" "+str(self.current_term) +" \n")


                # write to log file

        if leader_commit > self.commit_length:
            for i in range(self.commit_length, leader_commit):
                # deliver log[i].message to application
                # Commit Here
                # TODO : Check if correct or not
                message = self.log[i]["message"]
                if message.startswith("SET"):
                    _, key, value = message.split(" ")
                    self.data_truths[key] = value
                    with open("logs_node_"+str(self.node_id)+"/dump.txt", "a", newline="") as file:
                       file.write(" Node"+str(self.node_id) +" (follower) committed the entry "+message+" to the state machine \n")
                    print(" Node"+str(self.node_id) +" (follower) committed the entry "+message+" to the state machine ")
                    
            self.commit_length = leader_commit

            if os.path.isfile("logs_node_"+str(self.node_id)+"/metadata.txt"):
                os.remove("logs_node_"+str(self.node_id)+"/metadata.txt")
            with open("logs_node_"+str(self.node_id)+"/metadata.txt", "w") as file:
                file.write("Commit length "+str(self.commit_length)+" Term "+str(self.current_term)+" Node Voted For ID "+str(self.voted_for))

    def handle_log_response(self, follower_id, term, ack, success):
        """
        From Pseudocode 8/9
        """
        print("Handling Log Response from Follower "+ str(follower_id) + " for term "+str(term) + " ack "+str(ack) + " success "+str(success))
        follower_id = str(follower_id)
        if success:
            self.COUNT_OF_SUCCESSFUL_LEASE_RENEWALS += 1
            if self.COUNT_OF_SUCCESSFUL_LEASE_RENEWALS >= math.ceil((len(self.connections) + 1) / 2):
                self.cancel_timers()
                self.handle_timers()
        if term == self.current_term and self.current_role == "Leader":
            if success and ack >= self.acked_length[follower_id]:
                # print("Success and ack >= acked_length")
                self.acked_length[follower_id] = ack
                self.sent_length[follower_id] = ack
                self.commit_log_entries()
            elif self.sent_length[follower_id] > 0:
                # open dump
                with open("logs_node_"+str(self.node_id)+"/dump.txt", "a", newline="") as file:
                    file.write("Node "+str(self.node_id)+"  rejected AppendEntries RPC from "+str(follower_id)+ " hence reducing the sent length \n")
                self.sent_length[follower_id] -= 1
                self.replicate_log(self.node_id, follower_id)
        elif term > self.current_term:
            self.current_role = "Follower"
            self.current_term = term
            self.voted_for = None
            # Cancel election timer
            self.cancel_timers()
            self.handle_timers()

    def acks(self, length):
        """
        From Pseudocode 9/9
        """
        return sum(1 for ack in self.acked_length if int(ack) >= length)
    

    def commit_log_entries(self):
        """
        From Pseudocode 9/9
        """
        min_acks = math.ceil((len(self.connections) + 1) / 2)
        ready = {i for i in range(len(self.log)) if self.acks(i) >= min_acks}
        # print(self.acked_length, self.sent_length, self.log, self.commit_length, ready)
        max_ready_index_offset_handled = max(ready) + 1
        if len(ready) != 0 and max_ready_index_offset_handled + 1 > self.commit_length and self.log[max_ready_index_offset_handled - 1]["term"] == self.current_term:
            for i in range(self.commit_length, max_ready_index_offset_handled):
                last_message = self.log[i]["message"]
                # TODO why do we need to see SET - Update NVM
                if last_message.startswith("SET"):
                    _, key, value = last_message.split(" ")
                    self.data_truths[key] = value
                    with open("logs_node_"+str(self.node_id)+"/dump.txt", "a", newline="") as file:
                        file.write("Leader Node "+str(self.node_id)+" committed the entry "+last_message+" to the state machine \n")
                    print("Leader Node "+str(self.node_id)+" committed the entry "+last_message+" to the state machine ")
                    with open("logs_node_"+str(self.node_id)+"/logs.txt", "a", newline="") as file:
                        file.write(last_message +" "+self.current_term +" \n")
                    
                # deliver log[i].message to application
                # self.broadcast_messages(self.log[i]["message"])

                # On the next LogRequest message that the leader sends to followers, the new value of 
                # commitLength will be included, causing the followers to commit and deliver the same log entries.



            self.commit_length = max_ready_index_offset_handled
            if os.path.isfile("logs_node_"+str(self.node_id)+"/metadata.txt"):
                os.remove("logs_node_"+str(self.node_id)+"/metadata.txt")
            with open("logs_node_"+str(self.node_id)+"/metadata.txt", "w") as file:
                file.write("Commit length "+str(self.commit_length)+" Term "+str(self.current_term)+" Node ID "+str(self.voted_for))
        

if __name__=='__main__':
    max_client = 10
    argparser = argparse.ArgumentParser()
    argparser.add_argument("--nodeId", type=int)
    argparser.add_argument("--restarting", type=bool, default=False)
    nodeId = argparser.parse_args().nodeId
    restarting = argparser.parse_args().restarting
    print("Starting Node with ID " + str(nodeId))
    # node = RaftNode(nodeId, restarting)
    try:
        # node.main()
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_client))
        node_pb2_grpc.add_NodeServicer_to_server(RaftNode(nodeId,restarting), server)

        with open('connections_grpc.json') as f:
            connections = json.load(f)

        self_addr = connections[str(nodeId)]
        port = self_addr.split(":")[-1]
        print('Starting server. Listening on port '+port)
        server.add_insecure_port('[::]:'+port)
        server.start()
        server.wait_for_termination()
        # context = zmq.Context()
        # socket = context.socket(zmq.PUSH)
    # Our event handling part
        # monitor = socket.get_monitor_socket()
        # t = threading.Thread(target=event_monitor, args=(monitor,1,0))
        # t.start()
        # socket.connect("tcp://localhost:5556")
        # socket.send("message".encode())

    except KeyboardInterrupt:
        # node.timer.cancel()
        print("Exiting Node with ID " + str(nodeId))
        os._exit(0)