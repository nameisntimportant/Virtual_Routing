import socket, threading, time
from DataStructure import *

'''
	nodesInTopo:set(str)  # eg: {'D', 'B', 'C', 'A', 'E'}
	nodesAliveInTopo:set(str)  # eg: {'D', 'B', 'C', 'A', 'E'}
	edgesInTopo:dict{dict}  # eg: {'A': {'D': 60, 'E': 20, 'C': 80}}
	lastTimeRecvPktFromNode:dict  # eg: {'A': 1513933432.4340003, 'E': 1513933427.1768813}
'''
global nodesInTopo, nodesAliveInTopo, edgesInTopo, lastTimeRecvPktFromNode

TIMEOUT = 30

# 向所有路由器周期性地广播节点node的链路状态信息
def broadcast_link_state(node: Node):
	while True:
		node.print_Node_Header()
		print('SEND: broadcasting link state... ')

		for n in nodesInTopo:
			if n != node.name:
				n_addr = name2addr(n)
				sendpkt = Packet(node.address, n_addr, node.neighbors, 1)
				node.sendSocket.sendto(sendpkt.tojson().encode(), (n_addr.ip, n_addr.port))

		time.sleep(10)

# 启动周期性地广播链路状态的线程
def thread_broadcast_link_state(node: Node):
	t = threading.Thread(target=broadcast_link_state, args=(node,), name='thread_broadcast_link_state')#, name='BroadcastLinkStateThread')
	t.start()


# 监听是否收到数据包，并处理收到的数据包
def thread_listener(node: Node):
	t = threading.Thread(target=listener, args=(node,), name='thread_listener')#, name='UDPListenerThread')
	t.start()

def listener(node: Node):
	while True:
		data, addr = node.receiveSocket.recvfrom(1024)  # 接收数据
		# print('Received from %s:%s.' % addr)
		recvPkt = Packet()
		recvPkt.fromjson(bytes.decode(data))
	
		if recvPkt.packetType == 0:  # 0表示普通数据包，1表示OSPF的链路状态信息数据包,2表示该数据包是一条发送数据包的指令
			node.forward_normal_packet(recvPkt)
		elif recvPkt.packetType == 1:
			deal_link_state_packet(node, recvPkt)
		elif recvPkt.packetType == 2:
			node.send_normal_packet(name2addr(recvPkt.payload), 'Hello, I\'m ' + str(node.name) + '.', 0)


def deal_link_state_packet(node: Node, recvPkt: Packet):
	addr = recvPkt.src
	for nodeName in nodesInTopo:
		if addr == name2addr(nodeName):
			node_recv_from = nodeName
			break

	lock.acquire()
	try:
		lastTimeRecvPktFromNode[node_recv_from] = time.time()

		node.print_Node_Header()
		print('RECEIVE: LS packet. FROM: ', node_recv_from, recvPkt.src.port, recvPkt.packetType)
		
		nodesAliveInTopo.add(node_recv_from)
		node.print_Node_Header()
		print('alive nodes: ', nodesAliveInTopo)

	
		edgesInTopo[node_recv_from] = {}
		for n in recvPkt.payload.keys():
			edgesInTopo[node_recv_from][n] = recvPkt.payload[n][1]
	finally:
		lock.release()

	Dijkstra_algorithm(node)

 
def Dijkstra_algorithm(node: Node):
	okay = set([node.name])
	notOkay = nodesAliveInTopo.copy()
	notOkay.remove(node.name)

	# initialization
	Dist = {}
	prev_step = {}
	for v in notOkay:
		if v in node.neighbors:
			Dist[v] = edgesInTopo[node.name][v]
			prev_step[v] = node.name
		else:
			Dist[v] = float('inf')

	# loop
	while len(notOkay) > 0:
		min_node = ''
		min_cost = float('inf')
		for v in notOkay:
			if Dist[v] <= min_cost:
				min_cost = Dist[v]
				min_node = v

		notOkay.remove(min_node)
		okay.add(min_node)
		
		for v in notOkay:
			if v in edgesInTopo[min_node]:
				if Dist[v] > Dist[min_node] + edgesInTopo[min_node][v]:
					Dist[v] = Dist[min_node] + edgesInTopo[min_node][v]
					prev_step[v] = min_node
			elif min_node in edgesInTopo[v]:
				if Dist[v] > Dist[min_node] + edgesInTopo[v][min_node]:
					Dist[v] = Dist[min_node] + edgesInTopo[v][min_node]
					prev_step[v] = min_node

	construct_forwarding_table(node, prev_step)

	# print the new forwarding table
	node.print_Node_Header()
	print('UPDATE: Forwarding table updated. INFORTION:')
	node.print_LS_forwardingTable()



def construct_forwarding_table(node: Node, prev_step: dict):
	# construct forwarding table of the parameter'node'
	next_step_from_current_node = {}

	for x in prev_step.keys():
		if prev_step[x] == node.name:
			next_step_from_current_node[x] = x
		else:
			temp = x
			while prev_step[temp] != node.name:
				temp = prev_step[temp]
			next_step_from_current_node[x] = temp

	node.LS_forwardingTable.clear()
	for k in next_step_from_current_node.keys():
		node.LS_forwardingTable.append(LS_forwardingTableEntry(dest=k, nextHop=next_step_from_current_node[k]))


def thread_check_alive(node: Node):
	t = threading.Thread(target=check_alive, args=(node,), name='thread_check_alive')#, name='CheckNodesAliveThread')	
	t.start()

# 周期性地检查其他节点是否down掉
def check_alive(node: Node):
	while True:
		lock.acquire()
		try:

			aliveNodes = nodesAliveInTopo.copy()

			for nodeName in aliveNodes:
				if nodeName != node.name:
					if time.time() - lastTimeRecvPktFromNode[nodeName] > TIMEOUT:
						nodesAliveInTopo.remove(nodeName)
						node.print_Node_Header()
						print('WARNING: Node out of connect (30s). INFORMATION:', nodeName)
						Dijkstra_algorithm(node)
		finally:
			lock.release()

		time.sleep(10)






if __name__ == "__main__":
	nodesInTopo = set(['A', 'B', 'C', 'D', 'E'])
	nodesAliveInTopo = set()
	edgesInTopo = {}
	lastTimeRecvPktFromNode = {}

	nodeName = input('Name of this router: ')
	a = Node(nodeName)
	print('Router:', a.name, '[ IP:', a.address.ip, ', ReceivePort:', a.address.port, ']')

	nodesAliveInTopo.add(nodeName)
	edgesInTopo[nodeName] = {}
	for n in a.neighbors.keys():
		edgesInTopo[nodeName][n] = a.neighbors[n][1]


	lock = threading.Lock()


	thread_broadcast_link_state(a)
	thread_listener(a)
	thread_check_alive(a)