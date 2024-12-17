import random
import zmq
import argparse
import socket as s
import json
from typing import Any, Dict
from zmq.utils.monitor import recv_monitor_message
import threading
import time
leaderknown = False
leaderdown = False

EVENT_MAP = {}
for name in dir(zmq):
    if name.startswith('EVENT_'):
        value = getattr(zmq, name)
        EVENT_MAP[value] = name

def event_monitor(monitor: zmq.Socket,leader_id,leaderdown) -> None:
    while monitor.poll():
        evt: Dict[str, Any] = {}
        mon_evt = recv_monitor_message(monitor)
        evt.update(mon_evt)
        evt['description'] = EVENT_MAP[evt['event']]
        if evt['event'] == zmq.EVENT_CONNECT_RETRIED:
            print("Connection to Node "+str(leader_id)+" failed.")
            leaderdown = True
            break
    monitor.close()
    print()
    return leaderdown


def tcp_ping(address):
    _,host, port = address.split(":")
    host = host.replace("//", "")
    port = int(port)
    sock = s.socket(s.AF_INET, s.SOCK_STREAM)
    try:
        sock.settimeout(5)  # Timeout for the connection attempt
        # Connect to the server
        sock.connect((host, port))
        print(f"Successfully connected to {host}:{port}")
        sock.close()
        return False

    except s.error as e:
        print(f"Failed to connect to {host}:{port} - {e}")
        sock.close()
        return True


with open('connections_gcloud.json') as f:
    connections = json.load(f)

self_ip = "tcp://*:3359"
self_send_ip = "tcp://34.173.214.75:3359"
context = zmq.Context()
socket = context.socket(zmq.PUSH)

global_socket = context.socket(zmq.PULL)
global_socket.bind(self_ip)

checkPrevQuery = True

leader_id = None
# used as a check to see if the previous query was a completed
no_of_times_same_query = 0
while True:
    try:
        no_of_times_same_query += 1
        if leader_id == "None":
            leaderknown = False
        # write a zmq client which sends a message
        if checkPrevQuery or (no_of_times_same_query > 10):
            query = input("Enter type of query: Get or Set: ")
            print("Query: ", query)
            checkPrevQuery = False
            num_of_times_same_query = 0
        if not leaderknown or leader_id==None:
            leader_id = random.choice(list(connections.keys()))
            print("Sampled node : ", leader_id)
        query_parts = query.split()
        if query_parts[0].lower() == "set":
            if len(query_parts) != 3:
                print("Invalid query")
                checkPrevQuery = True
                continue
            queryToSend = query_parts[0].upper() + " " + query_parts[1] + " " + query_parts[2]+ " "+ self_send_ip

            leaderdown = False
            leaderdown = tcp_ping(connections[leader_id])
            if  leaderdown:
                print("Node is down")
                leaderknown = False
                continue
            socket = zmq.Context().socket(zmq.PUSH)
            socket.connect(connections[leader_id])
            socket.send(queryToSend.encode())
            # close the socket
            socket.close()

            message = global_socket.recv().decode()
            print("Received reply: ", message)
            reply_parts = message.split()
            if str(reply_parts[0]) == "1":
                print("Key set successfully")
                leaderknown = True
                checkPrevQuery = True
            else:
                print("Leader is node "+str(reply_parts[1]))
                leaderknown = True
                checkPrevQuery = False
                leader_id = str(reply_parts[1])
        elif query_parts[0].lower() == "get":
            if len(query_parts) != 2:
                print("Invalid query")
                checkPrevQuery = True
                continue
            queryToSend = query_parts[0].upper() + " " + query_parts[1] + " "+ self_send_ip
            leaderdown = False
            leaderdown = tcp_ping(connections[leader_id])
            if  leaderdown:
                print("Node is down")
                leaderknown = False
                continue
            socket = zmq.Context().socket(zmq.PUSH)
            socket.connect(connections[leader_id])
            socket.send(queryToSend.encode())
            # close the socket
            socket.close()
            message = global_socket.recv().decode()
            reply_parts = message.split()
            if str(reply_parts[0]) == "1":
                val = reply_parts[1]
                leaderknown = True
                checkPrevQuery = True
                print("Value of get "+str(query_parts)+" "+ str(val))
            elif str(reply_parts[0]) == "2":
                print("Key not found")
                leaderknown = True
                checkPrevQuery = True
            elif str(reply_parts[0]) == "0":
                print("Leader is node "+str(reply_parts[1]))
                leaderknown = True
                checkPrevQuery = False
                leader_id = str(reply_parts[1])
                if leader_id == "None":
                    leaderknown = False
        else:
            print("Invalid query")
            continue
    except Exception as e:
        print("Exception: ", e)
        global_socket = context.socket(zmq.PULL)
        global_socket.bind(self_ip)