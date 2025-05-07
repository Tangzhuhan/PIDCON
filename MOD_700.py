import struct
from dataclasses import dataclass
from typing import Dict, List
import serial
import time

@dataclass
class SensorConfig:
    address: int
    start_register: int
    num_registers: int
    command: bytes = None

def crc16(data):
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return crc

class ModbusSensor:
    def __init__(self, port, baudrate=9600, timeout=2):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial = None
        self.address = 0x02  # 默认设备地址
        self.sensors = {}  # 使用字典存储传感器配置
        self.connected = False  # 初始化为未连接状态
        print(f"正在初始化温度传感器，串口: {port}, 波特率: {baudrate}")
        self.connected = self.connect()  # 保存连接状态
        if self.connected:
            print("温度传感器初始化成功")
        else:
            print("温度传感器初始化失败")

    def connect(self):
        """连接串口"""
        try:
            if self.serial and self.serial.is_open:
                self.serial.close()
            
            print(f"正在打开串口 {self.port}...")
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout
            )
            
            # 等待串口初始化完成
            time.sleep(0.5)
            
            # 清空串口缓冲区
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            
            # 测试通信
            test_command = [0x02, 0x03, 0x00, 0x4A, 0x00, 0x01]
            crc = crc16(bytes(test_command))
            test_command.append(crc & 0xFF)
            test_command.append((crc >> 8) & 0xFF)
            
            print("发送测试命令...")
            self.serial.write(bytes(test_command))
            time.sleep(0.1)
            
            response = self.serial.read(7)
            if response and len(response) == 7:
                print("测试通信成功")
                return True
            else:
                print("测试通信失败")
                return False
                
        except Exception as e:
            print(f"连接温度传感器失败: {e}")
            print(f"错误类型: {type(e).__name__}")
            print(f"错误详情: {str(e)}")
            return False

    def is_open(self):
        """检查串口是否打开"""
        return self.serial is not None and self.serial.is_open

    def add_sensor(self, address, start_register, num_registers):
        """添加传感器到列表"""
        self.sensors[address] = SensorConfig(
            address=address,
            start_register=start_register,
            num_registers=num_registers
        )

    def get_sensor_command(self, address):
        """获取指定地址的传感器命令"""
        for sensor in self.sensors:
            if sensor['address'] == address:
                return self._create_read_command(
                    address,
                    sensor['start_register'],
                    sensor['num_registers']
                )
        return None

    def get_all_sensor_commands(self):
        """获取所有传感器的命令"""
        commands = []
        for sensor in self.sensors:
            commands.append(self._create_read_command(
                sensor['address'],
                sensor['start_register'],
                sensor['num_registers']
            ))
        return commands

    def get_sensor_addresses(self):
        """获取所有传感器的地址"""
        return [sensor['address'] for sensor in self.sensors]

    def send_command(self, command):
        """发送 Modbus 命令"""
        try:
            self.serial.write(command)
            response = self.serial.read(7)  # 读取响应
            return response
        except Exception as e:
            return None

    def calculate_crc(self, data):
        """计算CRC16校验码"""
        return self.crc16(data)

    def read_temperature(self, channel):
        """读取指定通道的温度值"""
        if not self.is_open():
            print("串口未打开，尝试重新连接...")
            if not self.connect():
                print("重新连接串口失败")
                return None
            else:
                print("重新连接串口成功")

        try:
            # 清空串口缓冲区
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            
            # 构建读取命令
            command = [
                channel,        # 设备地址（直接使用传感器编号）
                0x03,          # 功能码
                0x00,          # 起始地址高字节
                0x4A,          # 起始地址低字节
                0x00,          # 寄存器数量高字节
                0x01,          # 寄存器数量低字节
            ]
            
            # 计算CRC校验
            crc = crc16(bytes(command))
            command.append(crc & 0xFF)        # CRC低字节
            command.append((crc >> 8) & 0xFF) # CRC高字节
            
            # 打印发送的命令（用于调试）
            # print("\n" + "="*50)
            # print(f"发送命令 (传感器{channel}):")
            # print(f"原始数据: {bytes(command).hex().upper()}")
            # print(f"解析数据:")
            # print(f"  设备地址: 0x{command[0]:02X}")
            # print(f"  功能码: 0x{command[1]:02X}")
            # print(f"  起始地址: 0x{command[2]:02X}{command[3]:02X}")
            # print(f"  寄存器数量: 0x{command[4]:02X}{command[5]:02X}")
            # print(f"  CRC校验: 0x{command[6]:02X}{command[7]:02X}")
            
            # 发送命令
            self.serial.write(bytes(command))
            time.sleep(0.1)  # 等待100ms响应
            
            # 读取响应
            response = self.serial.read(7)  # 响应数据包长度为7字节
            if len(response) != 7:
                print(f"响应数据长度错误: 期望7字节，实际{len(response)}字节")
                print(f"响应数据: {response.hex().upper() if response else 'None'}")
                return None
            
            # 打印接收的响应（用于调试）
            # print(f"\n接收响应 (传感器{channel}):")
            # print(f"原始数据: {response.hex().upper()}")
            # print(f"解析数据:")
            # print(f"  设备地址: 0x{response[0]:02X}")
            # print(f"  功能码: 0x{response[1]:02X}")
            # print(f"  数据长度: 0x{response[2]:02X}")
            # print(f"  温度数据: 0x{response[3]:02X}{response[4]:02X}")
            # print(f"  CRC校验: 0x{response[5]:02X}{response[6]:02X}")
                
            # 解析响应
            if response[0] != channel:
                print(f"设备地址不匹配: 期望0x{channel:02X}，实际0x{response[0]:02X}")
                return None
            if response[1] != 0x03:
                print(f"功能码不匹配: 期望0x03，实际0x{response[1]:02X}")
                return None
            if response[2] != 0x02:
                print(f"数据长度错误: 期望0x02，实际0x{response[2]:02X}")
                return None
                
            # 提取温度值
            temp_high = response[3]
            temp_low = response[4]
            temperature = ((temp_high << 8) | temp_low) / 10.0
            
            # 验证CRC
            received_crc = (response[6] << 8) | response[5]
            calculated_crc = crc16(response[:5])
            if received_crc != calculated_crc:
                print(f"CRC校验错误: 期望0x{calculated_crc:04X}，实际0x{received_crc:04X}")
                return None
            
            print(f"\n传感器{channel}温度: {temperature}°C")
            print("="*50 + "\n")
            return temperature
            
        except Exception as e:
            print(f"读取传感器{channel}温度失败: {e}")
            print(f"错误类型: {type(e).__name__}")
            print(f"错误详情: {str(e)}")
            # 尝试重新连接串口
            if not self.is_open():
                print("温度传感器串口断开，尝试重新连接...")
                if not self.connect():
                    print("重新连接温度传感器失败")
            return None

    def close(self):
        """关闭串口"""
        try:
            if self.serial and self.serial.is_open:
                self.serial.close()
        except Exception as e:
            print(f"关闭温度传感器串口失败: {e}")

    def is_connected(self):
        """检查传感器是否已连接"""
        return self.connected and self.is_open()