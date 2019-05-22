# -*- coding: utf-8 -*-
"""
Created on Wed May 15 23:02:19 2019

@author: DELL
"""

# -*- coding:utf-8 -*-
# 采用RIP

import socket, threading, time
from DataStructure import *


'''
	lastTimeRecvPktFromNode:dict  # eg: {'A': 1513933432.4340003, 'E': 1513933427.1768813}
'''
global lastTimeRecvPktFromNode
TIMEOUT = 30

def send_dv(node:Node):
	node.print_Node_Header()
	print('SEND: sending DV after updating... ')

	for n in node.aliveNeighbors:

		if n != node.name:
			n_addr = name2addr(n)
			sendpkt = Packet(node.address, n_addr, node.DV_forwardingTable, 1)
			node.sendSocket.sendto(sendpkt.tojson().encode(), (n_addr.ip, n_addr.port))


# 相邻路由器周期性(30s)地交换距离向量
def send_dv_periodcally(node: Node):
	while True:
		node.print_Node_Header()
		print('SEND: sending DV periodcally... ')
		
		lock.acquire()
		try:
			for n in node.neighbors:
				if n != node.name:
					n_addr = name2addr(n)
					sendpkt = Packet(node.address, n_addr, node.DV_forwardingTable, 1)
					node.sendSocket.sendto(sendpkt.tojson().encode(), (n_addr.ip, n_addr.port))
		finally:
			lock.release()

		time.sleep(10)

# 启动周期性地交换距离向量的线程
def thread_send_dv_periodcally(node: Node):
	t = threading.Thread(target=send_dv_periodcally, args=(node,), name='thread_send_dv_periodcally')
	t.start()


# 监听是否收到数据包，并处理收到的数据包
def thread_listener(node: Node):
	t = threading.Thread(target=listener, args=(node,), name='thread_listener')#, name='UDPListenerThread')
	t.start()

def listener(node: Node):
	while True:
		data, addr = node.receiveSocket.recvfrom(1024)  # 接收数据
		recvPkt = Packet()
		recvPkt.fromjson(bytes.decode(data))

	
		if recvPkt.packetType == 0:  # 0表示普通数据包，1表示RIP响应报文数据包,2表示该数据包是一条发送数据包的指令
			# handle_receiving_normal_packet(node, recvPkt)
			node.forward_normal_packet(recvPkt)
		elif recvPkt.packetType == 1:
			deal_dv_packet(node, recvPkt)
		elif recvPkt.packetType == 2:
			# handle_receiving_command_packet(node, recvPkt)
			node.send_normal_packet(name2addr(recvPkt.payload), 'Hello, I\'m ' + str(node.name) + '.', 0)


# def handle_receiving_normal_packet(node: Node, recvPkt: Packet):
# 	node.forward_normal_packet(recvPkt)


def deal_dv_packet(node: Node, recvPkt: Packet):
	node_recv_from = addr2name(recvPkt.src)

	node.print_Node_Header()
	print('RECEIVE: DV pkt INFORMATION:', node_recv_from)

	lock.acquire()
	try:

		if node_recv_from in node.neighbors.keys():
			node.aliveNeighbors.add(node_recv_from)

		lastTimeRecvPktFromNode[node_recv_from] = time.time()

		tempTable = node.DV_forwardingTable.copy()
		changeRoutingTable = False

		# 合并节点自己的RIP表和收到的RIP表
		for i in range(len(recvPkt.payload)):
			isInNodeRoutingTable = False
			recvEntry = DV_forwardingTableEntry(recvPkt.payload[i]['dest'], recvPkt.payload[i]['nextHop'], recvPkt.payload[i]['hopsToDest'])

			for j in range(len(tempTable)):
				
				# 收到的RIP表中和节点自己的RIP表dest相同的条目
				if recvEntry.dest == tempTable[j].dest:
					isInNodeRoutingTable = True

					if recvEntry.hopsToDest < tempTable[j].hopsToDest-1:
						node.DV_forwardingTable[j].nextHop = addr2name(recvPkt.src)
						node.DV_forwardingTable[j].hopsToDest = recvEntry.hopsToDest + 1
						changeRoutingTable = True
					else:
						if tempTable[j].nextHop == addr2name(recvPkt.src):
							if node.DV_forwardingTable[j].hopsToDest != recvEntry.hopsToDest + 1:
								node.DV_forwardingTable[j].hopsToDest = recvEntry.hopsToDest + 1
								changeRoutingTable = True
								
								if node.DV_forwardingTable[j].hopsToDest > 16:
									node.DV_forwardingTable[j].hopsToDest = 16

								

			# 收到的RIP表中和节点自己的RIP表dest不同的条目
			if not isInNodeRoutingTable:
				recvEntry.nextHop = node_recv_from
				recvEntry.hopsToDest += 1

				if recvEntry.hopsToDest > 16:
					recvEntry.hopsToDest = 16

				node.DV_forwardingTable.append(recvEntry)
				changeRoutingTable = True


		# 更新本地路由后，向相邻的的alive的节点发送distance vector
		if changeRoutingTable:
			send_dv(node)

			# print the new routing table
			node.print_Node_Header()
			print('UPDATE: Routing table updated. INFORMATION:')
			node.print_DV_forwardingTable()

	finally:
		lock.release()


# def handle_receiving_command_packet(node: Node, recvPkt: Packet):
# 	node.send_normal_packet(name2addr(recvPkt.payload), 'Hello, I\'m ' + str(node.name) + '.', 0)


def thread_check_alive(node: Node):
	t = threading.Thread(target=check_alive, args=(node,), name='thread_check_alive')#, name='CheckNeighborNodesAliveThread')	
	t.start()

# 周期性地检查其他节点是否down掉
def check_alive(node: Node):
	while True:
		lock.acquire()
		try:
			# node.print_Node_Header()
			# print('periodcally check..., alive neighbors:', node.aliveNeighbors)

			aliveNodes = node.aliveNeighbors.copy()

			for nodeName in aliveNodes:
				if time.time() - lastTimeRecvPktFromNode[nodeName] > TIMEOUT:

					node.print_Node_Header()
					print('WARNING: Node out of connect (30s). INFORMATION:', nodeName)
					node.aliveNeighbors.remove(nodeName)

					
					# 采用 "毒性反转" 解决路由环路
					#  当一条路径信息变为无效之后，路由器并不立即将它从路由表中删除，而是用16，即不可达的度量值将它广播出去。
					for i in range(len(node.DV_forwardingTable)):
						if node.DV_forwardingTable[i].dest == nodeName or node.DV_forwardingTable[i].nextHop == nodeName:
							node.DV_forwardingTable[i].hopsToDest = 16

					# 更新本地路由后，向相邻的的alive的节点发送distance vector
					send_dv(node)
					# print the new routing table
					node.print_Node_Header()
					print('UPDATE: Routing table updated. INFORMATION:')
					node.print_DV_forwardingTable()

		finally:
			lock.release()

		time.sleep(10)





if __name__ == "__main__":
	lastTimeRecvPktFromNode = {}

	nodeName = input('Name of this router: ')
	a = Node(nodeName)
	print('ROUTER:', a.name, '[ IP:', a.address.ip, ', ReceivePort:', a.address.port, ']')

	a.DV_forwardingTable.append(DV_forwardingTableEntry(dest=nodeName, nextHop='-', hopsToDest=0))
	
	a.aliveNeighbors = set()

	lock = threading.Lock()
	thread_listener(a)
	thread_check_alive(a)
	thread_send_dv_periodcally(a)