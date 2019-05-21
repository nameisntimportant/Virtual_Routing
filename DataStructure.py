import json
import socket, time

routerA = {'IP':'172.18.145.185', 'PORT':30001}
routerB = {'IP':'192.168.43.211', 'PORT':30002}
routerC = {'IP':'192.168.43.211', 'PORT':30003}
routerD = {'IP':'192.168.43.211', 'PORT':30004}
routerE = {'IP':'192.168.43.211', 'PORT':30005}
router = {'A':routerA, 'B':routerB, 'C':routerC, 'D':routerD, 'E':routerE, }

cost = {'A':{'A':0, 'B':-1, 'C':80, 'D':60,'E':20},
'B':{'A':-1, 'B':0, 'C':-1, 'D':50, 'E':70},
'C':{'A':80, 'B':-1, 'C':0, 'D':60, 'E':-1},
'D':{'A':60, 'B':50, 'C':60, 'D':0, 'E':-1},
'E':{'A':20, 'B':70, 'C':-1, 'D':-1, 'E':0}}

class Address():
	def __init__(self, ip, port:int):
		self.ip = ip
		self.port = port

	def __eq__(self, another):
		return self.ip == another.ip and self.port == another.port

	def __str__(self):
		return 'IP: ' + str(self.ip) + 'PORT: ' + str(self.port)


class Packet():
	def __init__(self, src:Address=None, dest:Address=None, payload=None, packetType:int=None):
		self.src = src
		self.dest = dest
		self.payload = payload
		self.packetType = packetType  	# 0表示普通数据包，1表示OSPF的链路状态信息数据包,2表示该数据包是一条发送数据包的指令

	# 序列化之后，就可以把序列化后的内容写入磁盘，或者通过网络传输到别的机器上
	def tojson(self):
		return json.dumps(self, default=lambda obj: obj.__dict__)

	def fromjson(self, pktjson):
		d = json.loads(pktjson)
		self.src = Address(d['src']['ip'], d['src']['port'])
		self.dest = Address(d['dest']['ip'], d['dest']['port'])
		self.payload = d['payload']
		self.packetType = int(d['packetType'])


class OSPF_ForwardingTableEntry():
	def __init__(self, dest:str=None, nextHop:str=None):
		self.dest = dest
		self.nextHop = nextHop

	def __str__(self):
		return "( " + str(self.dest) + ", " + str(self.nextHop) + " )"


class RIP_RoutingTableEntry():
	def __init__(self, dest:str=None, nextHop:str=None, hopsToDest:int=0):
		self.dest = dest
		self.nextHop = nextHop
		self.hopsToDest = hopsToDest

	def __str__(self):
		return "( " + str(self.dest) + ", " + str(self.nextHop) + ", " + str(self.hopsToDest) + " )"




def addr2name(addr: Address):
	for nodeName in {'D', 'B', 'C', 'A', 'E'}:  # ...................
		if addr == name2addr(nodeName):
			return nodeName


def name2addr(name):	
	return Address(router[name]['IP'],router[name]['PORT'])


def get_node_neighbors(name):
	neighbors = {}
	for key in cost[name].keys():
		if cost[name][key] > 0:
			neighbors[key] = (name2addr(key), cost[name][key])
	return neighbors


class Node():
	'''
	name: str  # eg: 'A', 'B'
	address: Address
	neighbors: dict  # eg: {'D': (<__main__.Address object at 0x7f3c575d7a90>, 60), 'E': (<__main__.Address object at 0x7f3c575d7ac8>, 20), 'C': (<__main__.Address object at 0x7f3c575d7a58>, 80)}
	socket: socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	'''
	def __init__(self, name):
		self.name = name
		self.address = name2addr(name)
		self.neighbors = get_node_neighbors(name)
		
		self.receiveSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  #  采用UDP
		self.receiveSocket.bind((self.address.ip, self.address.port))  # 用于接收数据，相当于UDP server
		self.sendSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # 用于发送数据

		self.OSPF_forwardingTable = []
		self.RIP_routingTable = []


	def printOutputMessageHeader(self):
		print(' '+self.name + ' - ' + time.strftime("%H:%M:%S", time.localtime()) + ' - ', end='')


	def printOSPFForwardingTable(self):
		print('        ' + self.name, 'Forwarding Table: ( dest, next )', )
		for i in range(len(self.OSPF_forwardingTable)):
			print(i, '                            ', self.OSPF_forwardingTable[i])


	def printRIPRoutingTable(self):
		print('        ' + self.name, 'Forwarding Table: ( dest, next, hops )')
		for i in range(len(self.RIP_routingTable)):
			print(i, '                           ', self.RIP_routingTable[i])


	def send_normal_packet(self, dest:Address, payload, packetType):
		sendpkt = Packet(self.address, dest, payload, packetType)
		self.forward_normal_packet(sendpkt)


	def forward_normal_packet(self, recvPkt: Packet):
		packetDest = addr2name(recvPkt.dest)
		packetSrc = addr2name(recvPkt.src)

		if packetDest == self.name:
			self.printOutputMessageHeader()
			print('RECEIVE: Normal packet. [', 'FROM:', packetSrc, ']', '. INFORMATION:', recvPkt.payload)
			# response
		else:
			# OSPF查找自己的forwarding table
			if self.OSPF_forwardingTable:
				for i in range(len(self.OSPF_forwardingTable)):

					if self.OSPF_forwardingTable[i].dest == packetDest:
						nextHopAddr = name2addr(self.OSPF_forwardingTable[i].nextHop)
						self.sendSocket.sendto(recvPkt.tojson().encode(), (nextHopAddr.ip, nextHopAddr.port))

						self.printOutputMessageHeader()
						if packetSrc == self.name:
							print('SEND: Normal packet. [ TO:', packetDest, ', NEXT-HOP:', self.OSPF_forwardingTable[i].nextHop, ']', '. INFORMATION:', recvPkt.payload)
						else:
							print('SEND: Forwarding normal packet. [', 'FROM:', packetSrc,', TO:', packetDest,  ', NEXT-HOP:', self.OSPF_forwardingTable[i].nextHop, ']')

			# RIP
			elif self.RIP_routingTable:
				for i in range(len(self.RIP_routingTable)):

					if self.RIP_routingTable[i].dest == packetDest:
						nextHopAddr = name2addr(self.RIP_routingTable[i].nextHop)
						self.sendSocket.sendto(recvPkt.tojson().encode(), (nextHopAddr.ip, nextHopAddr.port))

						self.printOutputMessageHeader()
						if packetSrc == self.name:
							print('SEND: Normal packet. [ TO:', packetDest, ', NEXT-HOP:', self.RIP_routingTable[i].nextHop, ']', ', CONTENT:', recvPkt.payload)
						else:
							print('SEND: Forwarding a normal packet. [', 'FROM:', packetSrc,', TO:', packetDest,  ', NEXT-HOP:', self.RIP_routingTable[i].nextHop, ']')
