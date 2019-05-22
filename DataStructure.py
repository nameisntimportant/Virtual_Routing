import json
import socket, time

# 各个路由器的IP以及端口
routerA = {'IP':'172.18.145.185', 'PORT':30001}
routerB = {'IP':'172.26.85.30', 'PORT':30002}
routerC = {'IP':'172.26.85.30', 'PORT':30003}
routerD = {'IP':'172.26.85.30', 'PORT':30004}
routerE = {'IP':'172.26.85.30', 'PORT':30005}
router = {'A':routerA, 'B':routerB, 'C':routerC, 'D':routerD, 'E':routerE }
# 拓扑图邻接矩阵
cost = {'A':{'A': 0, 'B':-1, 'C':80, 'D':60, 'E':20},
        'B':{'A':-1, 'B': 0, 'C':-1, 'D':50, 'E':70},
        'C':{'A':80, 'B':-1, 'C': 0, 'D':60, 'E':-1},
        'D':{'A':60, 'B':50, 'C':60, 'D': 0, 'E':-1},
        'E':{'A':20, 'B':70, 'C':-1, 'D':-1, 'E': 0}}

class Address():
	def __init__(self, ip, port:int):# 类构造函数
		self.ip = ip
		self.port = port

	def __eq__(self, another): # 重载相等条件，IP和port相等时类相等
		return self.ip == another.ip and self.port == another.port

	def __str__(self): # 转换为str的格式
		return 'IP: ' + str(self.ip) + 'PORT: ' + str(self.port)


class Packet():
	def __init__(self, src:Address=None, dest:Address=None, payload=None, packetType:int=None):
		self.src = src
		self.dest = dest
		self.payload = payload
		self.packetType = packetType  	# 数据包类型 0-普通数据包,1-链路状态信息,2-发送数据包的指令数据包

	def tojson(self): # 类转json
		return json.dumps(self, default=lambda obj: obj.__dict__)

	def fromjson(self, pktjson): # json转类
		d = json.loads(pktjson)
		self.src = Address(d['src']['ip'], d['src']['port'])
		self.dest = Address(d['dest']['ip'], d['dest']['port'])
		self.payload = d['payload']
		self.packetType = int(d['packetType'])


class LS_forwardingTableEntry(): # LS转发表中的一项
	def __init__(self, dest:str=None, nextHop:str=None):
		self.dest = dest
		self.nextHop = nextHop

	def __str__(self):
		return '     {0}               {1}'.format(self.dest,self.nextHop)


class DV_forwardingTableEntry(): # DV转发表中的一项
	def __init__(self, dest:str=None, nextHop:str=None, hopsToDest:int=0):
		self.dest = dest
		self.nextHop = nextHop
		self.hopsToDest = hopsToDest

	def __str__(self):
		return '     {0}                {1}             {2}'.format(self.dest,self.nextHop,self.hopsToDest)


def addr2name(addr: Address): # 由地址找编号
	for nodeName in {'D', 'B', 'C', 'A', 'E'}:  # ...................
		if addr == name2addr(nodeName):
			return nodeName

def name2addr(name): # 由编号找地址
	return Address(router[name]['IP'],router[name]['PORT'])

def get_neighbors(name): # 由cost表找邻居
	neighbors = {}
	for key in cost[name].keys():
		if cost[name][key] > 0:
			neighbors[key] = (name2addr(key), cost[name][key])
	return neighbors

class Node():
	'''构造函数'''
	def __init__(self, name): 
		self.name = name                           # 节点编号(A,B,C,D,E)
		self.address = name2addr(name)             # 节点地址
		self.neighbors = get_neighbors(name)  # 节点邻居的地址与边的权重
		self.LS_forwardingTable = []               # LS的转发表
		self.DV_forwardingTable = []               # DV的转发表
		
		self.receiveSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # 创建一个UDP套接字用于接收信息
		self.receiveSocket.bind((self.address.ip, self.address.port))  
		self.sendSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # 创建一个UDP套接字用于发送信息

	'''打印节点信息'''
	def print_Node_Header(self): # 如：A - 17:47:05 - 
		print(' '+self.name + ' - ' + time.strftime("%H:%M:%S", time.localtime()) + ' - ', end='')

	'''打印LS转发表'''
	def print_LS_forwardingTable(self): 
		print('              ' + self.name, 'Forwarding Table: ', )
		print('                Destination        Next_Hop')
		for i in range(len(self.LS_forwardingTable)):
			print('               ', self.LS_forwardingTable[i])

	'''打印DV转发表'''
	def print_DV_forwardingTable(self):
		print('              ' + self.name, 'Forwarding Table: ')
		print('                Destination        Next_Hop        Hops')
		for i in range(len(self.DV_forwardingTable)):
			print('               ', self.DV_forwardingTable[i])

	'''发送非节点状态信息包'''
	def send_normal_packet(self, dest:Address, payload, packetType):
		sendpkt = Packet(self.address, dest, payload, packetType) # 构造数据包
		self.forward_normal_packet(sendpkt) # 对本机调用转发函数发送数据包

	'''转发非节点状态信息包'''
	def forward_normal_packet(self, recvPkt: Packet): 
		packetDest = addr2name(recvPkt.dest)
		packetSrc = addr2name(recvPkt.src)

		if packetDest == self.name: # 本机为目的地址
			self.print_Node_Header()
			print('RECEIVE: Normal packet. [', 'FROM:', packetSrc, ']', '. INFORMATION:', recvPkt.payload)
		else:
			if self.LS_forwardingTable: # LS算法的数据包
				for i in range(len(self.LS_forwardingTable)):
					if self.LS_forwardingTable[i].dest == packetDest: # 搜索目的地IP
						nextHopAddr = name2addr(self.LS_forwardingTable[i].nextHop) # 读取LS转发表对应下一跳地址
						self.sendSocket.sendto(recvPkt.tojson().encode(), (nextHopAddr.ip, nextHopAddr.port))
						self.print_Node_Header()
						if packetSrc == self.name: # 执行发数据包动作时打印
							print('SEND: Normal packet. [ TO:', packetDest, ', NEXT-HOP:', self.LS_forwardingTable[i].nextHop, ']', '. INFORMATION:', recvPkt.payload)
						else: # 执行传递数据包动作时打印
							print('SEND: Forwarding normal packet. [', 'FROM:', packetSrc,', TO:', packetDest,  ', NEXT-HOP:', self.LS_forwardingTable[i].nextHop, ']')

			elif self.DV_forwardingTable: # DV算法的数据包
				for i in range(len(self.DV_forwardingTable)):
					if self.DV_forwardingTable[i].dest == packetDest:
						nextHopAddr = name2addr(self.DV_forwardingTable[i].nextHop)
						self.sendSocket.sendto(recvPkt.tojson().encode(), (nextHopAddr.ip, nextHopAddr.port))
						self.print_Node_Header()
						if packetSrc == self.name:
							print('SEND: Normal packet. [ TO:', packetDest, ', NEXT-HOP:', self.DV_forwardingTable[i].nextHop, ']', ', CONTENT:', recvPkt.payload)
						else:
							print('SEND: Forwarding a normal packet. [', 'FROM:', packetSrc,', TO:', packetDest,  ', NEXT-HOP:', self.DV_forwardingTable[i].nextHop, ']')
