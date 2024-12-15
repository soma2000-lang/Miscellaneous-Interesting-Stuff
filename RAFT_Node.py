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

class RaftNode:
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

        # Read connections.json
        with open('connections.json') as f:
            self.connections = json.load(f)

        self_addr = self.connections[str(node_id)]

        self_addr = self_addr.replace("localhost", "*")

        self.self_addr = self_addr

        del self.connections[str(node_id)]

        for key in self.connections:
            self.sent_length[key] = 0
            self.acked_length[key] = 0

        self.global_zmq_socket = zmq.Context().socket(zmq.PULL)
        self.global_zmq_socket.bind(self_addr)

        # Check if folder exists else create it
        if not os.path.exists("logs_node_"+str(node_id)):
            os.makedirs("logs_node_"+str(node_id))

        if restarting == False:
            if os.path.isfile("logs_node_"+str(node_id)+"/logs.txt"):
                os.remove("logs_node_"+str(node_id)+"/logs.txt")
            if os.path.isfile("logs_node_"+str(node_id)+"/metadata.txt"):
                os.remove("logs_node_"+str(node_id)+"/metadata.txt")
            if os.path.isfile("logs_node_"+str(node_id)+"/dump.txt"):
                os.remove("logs_node_"+str(node_id)+"/dump.txt")
        else:
            self.restarting_node()

        

        # if dump.txt doesn't exist create it and don't write anything
        if not os.path.isfile("logs_node_"+str(node_id)+"/dump.txt"):
            with open("logs_node_"+str(node_id)+"/dump.txt", "w") as file:
                pass

        self.MAX_LEASE_TIMER_LEFT = 7
        self.HEARTBEAT_TIMEOUT = 1
        self.COUNT_OF_SUCCESSFUL_LEASE_RENEWALS = 1

        self.LEADER_TIME_LEFT = 0

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
                log = log.strip()
                chunks = log.split(" ")
                term = int(chunks[-1])
                message = " ".join(chunks[:-1])
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
        # print("handle timers called", self.current_role)
        if self.current_role == 'Leader':
            self.timer = MyTimer(self.HEARTBEAT_TIMEOUT, self.periodic_heartbeat)
            self.timer.start()
            self.lease_timer = MyTimer(self.MAX_LEASE_TIMER_LEFT, self.step_down)
            self.lease_timer.start()
        elif self.current_role != 'Leader' and not converting_to_leader:
            MIN_TIMEOUT = 10
            MAX_TIMEOUT = 20
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
            self.current_leader = "None"
            self.cancel_timers()
            self.handle_timers()

    def main(self):
        iteration = 0
        while True:
            try:
                message = self.global_zmq_socket.recv().decode()
            except Exception as e:
                print("Exception: ", e)
                self.global_zmq_socket = zmq.Context().socket(zmq.PULL)
                self.global_zmq_socket.bind(self.self_addr)
                continue
            message_parts = message.split(" ")
            if message_parts[0] == "VoteRequest":
                cId, cTerm, cLogLength, cLogTerm = message_parts[1:]
                self.handle_vote_request(int(cId), int(cTerm), int(cLogLength), int(cLogTerm))
            elif message_parts[0] == "VoteResponse":
                voterId, term, granted, lease_timer_left_according_to_voter = message_parts[1:]
                self.handle_vote_response(int(voterId), int(term), granted == "True", float(lease_timer_left_according_to_voter))
            elif message_parts[0] == "LogRequest":
                leader_id, term, prefix_len, prefix_term, leader_commit = message_parts[1:6]
                lease_timer_left_according_to_leader = message_parts[-1]
                suffix = message_parts[6:-1]
                suffix = " ".join(suffix)
                suffix = eval(suffix)
                lease_timer_left_according_to_leader = float(lease_timer_left_according_to_leader)
                self.handle_log_request(int(leader_id), int(term), int(prefix_len), int(prefix_term), int(leader_commit), suffix, lease_timer_left_according_to_leader)
            elif message_parts[0] == "LogResponse":
                follower_id, term, ack, success = message_parts[1:]
                self.handle_log_response(int(follower_id), int(term), int(ack), success == "True")
            elif message_parts[0] == "Forward":
                node_id, current_term, message = message_parts[1:]
                self.broadcast_messages(message)
            elif message_parts[0] == "GET":
                key = message_parts[1]
                return_address = message_parts[2]
                status, returnVal = self.get_query(key)
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

    def get_query(self, key):
        if self.current_role == "Leader":
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


    def leader_failed_or_election_timeout(self):
        """
        From Pseudocode 1/9
        """
        with open("logs_node_"+str(self.node_id)+"/dump.txt", "a", newline="") as file:
            file.write("Node "+str(self.node_id)+" election timer timed out, Starting election. \n")

        print("Node "+str(self.node_id)+" election timer timed out, Starting election. ")
        self.current_term += 1
        self.current_role = "Candidate"
        self.voted_for = self.node_id
        self.votes_received = {self.node_id}
        last_term = 0
        self.current_leader = "None"
        if len(self.log) > 0:
            last_term = self.log[-1]["term"]
        message = "VoteRequest " + str(self.node_id) + " " + str(self.current_term) + " " + str(len(self.log)) + " " + str(last_term)
        for n_id, connection in self.connections.items():
            context = zmq.Context()
            socket = context.socket(zmq.PUSH)
            monitor = socket.get_monitor_socket()
            t = threading.Thread(target=event_monitor, args=(monitor,self.node_id,n_id))
            t.start()
            socket.connect(connection)
            socket.send(message.encode())
        self.cancel_timers()
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
            message = "VoteResponse " + str(self.node_id) + " " + str(self.current_term) + " " + str(True)  + " " + str(self.LEADER_TIME_LEFT)
            candidate_socket_addr = self.connections[str(cId)]
            context = zmq.Context()
            candidate_socket = context.socket(zmq.PUSH)
            monitor = candidate_socket.get_monitor_socket()
            t = threading.Thread(target=event_monitor, args=(monitor,self.node_id,cId))
            t.start()
            candidate_socket.connect(candidate_socket_addr)
            candidate_socket.send(message.encode())
            with open("logs_node_"+str(self.node_id)+"/dump.txt", "a", newline="") as file:
                file.write("Vote Granted for Node "+str(cId)+" in term."+str(cTerm) +"\n")
            print("Vote Granted for Node "+str(cId)+" in term."+str(cTerm))
        else:
            # Reply no vote
            time_left_in_leader_lease = self.lease_timer.remaining()
            message = "VoteResponse " + str(self.node_id) + " " + str(self.current_term) + " " + str(False) + " " + str(time_left_in_leader_lease)
            candidate_socket_addr = self.connections[str(cId)]
            context = zmq.Context()
            candidate_socket = context.socket(zmq.PUSH)
            monitor = candidate_socket.get_monitor_socket()
            t = threading.Thread(target=event_monitor, args=(monitor,self.node_id,cId))
            t.start()
            candidate_socket.connect(candidate_socket_addr)
            candidate_socket.send(message.encode())
            with open("logs_node_"+str(self.node_id)+"/dump.txt", "a", newline="") as file:
                file.write("Vote denied for Node "+str(cId)+" in term."+str(cTerm) +"\n")
            print("Vote denied for Node "+str(cId)+" in term."+str(cTerm))
        self.handle_timers()
    
    def handle_vote_response(self, voterId, term, granted, lease_timer_left_according_to_voter):
        """
        From Pseudocode 3/9
        """
        self.LEADER_TIME_LEFT = max(self.LEADER_TIME_LEFT, lease_timer_left_according_to_voter)

        if self.current_role == 'Candidate' and term == self.current_term and granted:
            self.votes_received.add(voterId)
            if len(self.votes_received) >= math.ceil((len(self.connections) + 1) / 2):
                # Sleep for the max known lease
                print("Going to Sleep before becoming leader")
                print("Current Time:", time.time())
                s_time = time.time()
                time.sleep(self.LEADER_TIME_LEFT)
                print("Time when woke up", time.time())
                e_time = time.time()
                print("Slept for ", e_time - s_time , " expected was ", self.LEADER_TIME_LEFT)
                print("Woke up")
                self.current_role = "Leader"
                with open("logs_node_"+str(self.node_id)+"/dump.txt", "a", newline="") as file:
                    file.write("Node "+str(self.node_id)+" became the leader for term "+str(term)+"\n")
                print("Node "+str(self.node_id)+" became the leader for term "+str(term))
                self.current_leader = self.node_id
                self.cancel_timers()
                self.handle_timers()
                for follower, _ in self.connections.items():
                    self.sent_length[follower] = len(self.log)
                    self.acked_length[follower] = 0
                    self.replicate_log(self.node_id, follower)

                self.broadcast_messages("No-OP")
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
            self.acked_length[str(self.node_id)] = len(self.log)
            self.COUNT_OF_SUCCESSFUL_LEASE_RENEWALS = 1
            for follower, _ in self.connections.items():
                self.replicate_log(self.node_id, follower)
        else:
            # Forward to Leader
            context = zmq.Context()
            socket = context.socket(zmq.PUSH)
            socket.connect(self.connections[self.current_leader])
            monitor = socket.get_monitor_socket()
            t = threading.Thread(target=event_monitor, args=(monitor,1,0))
            t.start()
            message = "Forward " + str(self.node_id) + " " + str(self.current_term) + " " + message
            socket.send(message.encode())

    def periodic_heartbeat(self):
        """
        From Pseudocode 4/9
        """
        if self.current_role == "Leader":
            with open("logs_node_"+str(self.node_id)+"/dump.txt", "a", newline="") as file:
                file.write("Leader "+str(self.node_id)+" sending heartbeat & Renewing Lease \n")
            print("Leader "+str(self.node_id)+" sending heartbeat & Renewing Lease ")
            self.COUNT_OF_SUCCESSFUL_LEASE_RENEWALS = 1
            for follower, _ in self.connections.items():
                self.replicate_log(self.node_id, follower)

    def replicate_log(self, leader_id, follower_id):
        """
        From Pseudocode 5/9
        """
        # Cancelling and restarting the timers otherwise the leader keeps getting timed out
        print("Replicating log from Leader "+str(leader_id)+" to Follower "+str(follower_id))
        prefix_len = self.sent_length[follower_id]
        suffix = self.log[prefix_len:]
        prefix_term = 0
        if prefix_len > 0:
            prefix_term = self.log[prefix_len - 1]["term"]
        lease_timer_left = self.lease_timer.remaining()
        message = "LogRequest " + str(leader_id) + " " + str(self.current_term) + " " + str(prefix_len) + " " + str(prefix_term) + " " + str(self.commit_length) + " " + str(suffix) + " " + str(lease_timer_left)
        context = zmq.Context()
        socket = context.socket(zmq.PUSH)
        monitor = socket.get_monitor_socket()
        t = threading.Thread(target=event_monitor, args=(monitor,self.node_id,follower_id))
        t.start()
        socket.connect(self.connections[follower_id])
        socket.send(message.encode())
        print("Replicated log from Leader "+str(leader_id)+" to Follower "+str(follower_id))

    def handle_log_request(self, leader_id, term, prefix_len, prefix_term, leader_commit, suffix, lease_timer_left_according_to_leader):
        """
        From Pseudocode 6/9
        """
        if self.current_role != "Leader":
            self.cancel_timers()
            self.handle_timers()
        self.LEADER_TIME_LEFT = lease_timer_left_according_to_leader
        if term > self.current_term:
            self.current_term = term
            self.voted_for = None
            self.cancel_timers()
            self.handle_timers()
        if term == self.current_term:
            self.current_role = "Follower"
            self.current_leader = leader_id
            self.cancel_timers()
            self.handle_timers()
        logOk = len(self.log) >= prefix_len and (prefix_len == 0 or self.log[prefix_len-1]["term"] == prefix_term)
        if term == self.current_term and logOk:
            self.append_entries(prefix_len, leader_commit, suffix)
            ack = prefix_len + len(suffix)
            log_response_message = "LogResponse " + str(self.node_id) + " " + str(self.current_term) + " " + str(ack) + " " + str(True)
        else:
            with open("logs_node_"+str(self.node_id)+"/dump.txt", "a", newline="") as file:
                    file.write("Node "+str(self.node_id)+"  rejected AppendEntries RPC from "+str(self.current_leader)+ "\n")
            print("Node "+str(self.node_id)+"  rejected AppendEntries RPC from "+str(self.current_leader))
            log_response_message = "LogResponse " + str(self.node_id) + " " + str(self.current_term) + " " + "0" + " " + str(False)
        candidate_socket_addr = self.connections[str(self.current_leader)]
        context = zmq.Context()
        candidate_socket = context.socket(zmq.PUSH)
        monitor = candidate_socket.get_monitor_socket()
        t = threading.Thread(target=event_monitor, args=(monitor,self.node_id,self.current_leader))
        t.start()
        candidate_socket.connect(candidate_socket_addr)
        candidate_socket.send(log_response_message.encode())


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
                last_message = suffix[i]
                last_message = last_message["message"]
                with open("logs_node_"+str(self.node_id)+"/logs.txt", "a", newline="") as file:
                    file.write(last_message +" "+str(self.current_term) +" \n")

        if leader_commit > self.commit_length:
            for i in range(self.commit_length, leader_commit):
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
        # Write to disk
        with open("logs_node_"+str(self.node_id)+"/dump.txt", "a", newline="") as file:
            file.write("Handling Log Response from Follower "+ str(follower_id) + " for term "+str(term) + " ack "+str(ack) + " success "+str(success) + "\n")
        print("Handling Log Response from Follower "+ str(follower_id) + " for term "+str(term) + " ack "+str(ack) + " success "+str(success))
        follower_id = str(follower_id)
        if success:
            self.COUNT_OF_SUCCESSFUL_LEASE_RENEWALS += 1
            if self.COUNT_OF_SUCCESSFUL_LEASE_RENEWALS >= math.ceil((len(self.connections) + 1) / 2):
                self.cancel_timers()
                self.handle_timers()
        if term == self.current_term and self.current_role == "Leader":
            if success and ack >= self.acked_length[str(follower_id)]:
                self.acked_length[str(follower_id)] = ack
                self.sent_length[str(follower_id)] = ack
                self.commit_log_entries()
            elif self.sent_length[str(follower_id)] > 0:
                # open dump
                with open("logs_node_"+str(self.node_id)+"/dump.txt", "a", newline="") as file:
                    file.write("Node "+str(self.node_id)+"  rejected AppendEntries RPC from "+str(follower_id)+ "hence reducing the sent length \n")
                self.sent_length[str(follower_id)] -= 1
                self.replicate_log(self.node_id, str(follower_id))
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
        return sum(1 for node_id, acks_from_that_node_id in self.acked_length.items() if int(acks_from_that_node_id) >= length)

    def commit_log_entries(self):
        """
        From Pseudocode 9/9
        """
        min_acks = math.ceil((len(self.connections) + 1) / 2)
        ready = {i for i in range(len(self.log)) if self.acks(i) >= min_acks}
        max_ready_index_offset_handled = max(ready) + 1
        [1,2,3,4]
        if len(ready) != 0 and max_ready_index_offset_handled + 1 > self.commit_length and self.log[max_ready_index_offset_handled - 1]["term"] == self.current_term:
            for i in range(self.commit_length, max_ready_index_offset_handled):
                if i >= len(self.log):
                    continue
                last_message = self.log[i]["message"]
                print("Committing message: ", last_message)
                if last_message.startswith("SET"):
                    _, key, value = last_message.split(" ")
                    self.data_truths[key] = value
                with open("logs_node_"+str(self.node_id)+"/dump.txt", "a", newline="") as file:
                    file.write("Leader Node "+str(self.node_id)+" committed the entry "+last_message+" to the state machine \n")
                print("Leader Node "+str(self.node_id)+" committed the entry "+last_message+" to the state machine ")
                with open("logs_node_"+str(self.node_id)+"/logs.txt", "a", newline="") as file:
                    file.write(last_message +" "+str(self.current_term) +" \n")

            self.commit_length = max_ready_index_offset_handled
        if os.path.isfile("logs_node_"+str(self.node_id)+"/metadata.txt"):
            os.remove("logs_node_"+str(self.node_id)+"/metadata.txt")
        with open("logs_node_"+str(self.node_id)+"/metadata.txt", "w") as file:
            file.write("Commit length "+str(self.commit_length)+" Term "+str(self.current_term)+" Node ID "+str(self.voted_for))
        

if __name__=='__main__':
    argparser = argparse.ArgumentParser()
    argparser.add_argument("--nodeId", type=int)
    argparser.add_argument("--restarting", type=bool, default=False)
    nodeId = argparser.parse_args().nodeId
    restarting = argparser.parse_args().restarting
    print("Starting Node with ID " + str(nodeId))
    node = RaftNode(nodeId, restarting)
    try:
        node.main()
    except KeyboardInterrupt:
        node.timer.cancel()
        print("Exiting Node with ID " + str(nodeId))
        os._exit(0)