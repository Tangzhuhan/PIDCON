from MOD_700 import ModbusSensor
from power import PowerSupply
import time
from collections import deque

class PIDController:
    def __init__(self):
        """初始化PID控制器"""
        # PID参数
        self.kp = 0.2  # 增加比例系数，使响应更快
        self.ki = 0.002  # 增加积分系数，增强积分作用
        self.kd = 0.005  # 减小微分系数，使系统对温度变化的响应更平缓
        self.setpoint = 0.0
        self.last_error = 0.0
        self.integral = 0.0
        self.sampling_rate = 1000  # 采样率（毫秒）
        self.initial_voltage = 0.0  # 初始电压
        self.max_voltage = 17.0  # 最大电压限制
        self.warmup_time = 30  # 预热时间（秒）
        self.duration = 0.0  # 控制持续时间（秒）
        self.temp_error = 0.1  # 温度误差范围
        
        # 死区控制参数
        self.dead_zone = 1.0  # 死区范围（°C）
        self.in_dead_zone = False  # 是否在死区内
        self.dead_zone_voltage = 0.0  # 死区内的固定电压值
        
        # 控制状态
        self.is_running = False
        self.is_paused = False
        self.start_time = None
        self.warmup_start_time = None  # 预热开始时间
        self.is_warmup = False  # 是否在预热阶段
        
        # 设备连接
        self.modbus_sensor = None
        self.power_supply = None
        
        # 传感器选择
        self.selected_sensors = []
        self.main_sensor = None
        
        # 初始化数据存储
        self.time_data = []  # 使用列表而不是deque
        self.system_time_data = []  # 使用列表而不是deque
        self.voltage_data = []  # 使用列表而不是deque
        self.current_data = []  # 使用列表而不是deque
        self.temperature_data = {}  # 使用字典存储温度数据列表
        
        # 初始化预热数据存储
        self.warmup_time_data = []
        self.warmup_system_time_data = []
        self.warmup_voltage_data = []
        self.warmup_current_data = []
        self.warmup_temperature_data = {}
        
        print("PID控制器初始化完成")

    def set_pid_params(self, kp, ki, kd):
        """设置PID参数"""
        self.kp = kp
        self.ki = ki
        self.kd = kd

    def set_target_temp(self, setpoint):
        """设置目标温度"""
        self.setpoint = setpoint

    def set_initial_voltage(self, voltage):
        """设置初始电压"""
        self.initial_voltage = voltage

    def set_temp_error(self, error):
        """设置温度误差范围"""
        self.temp_error = error

    def set_duration(self, duration):
        """设置目标持续时间（分钟）"""
        self.duration = duration * 60  # 转换为秒

    def set_sampling_rate(self, rate):
        """设置采样率（毫秒）"""
        try:
            self.sampling_rate = float(rate)
        except (ValueError, TypeError):
            print(f"警告: 采样率 {rate} 不是有效的数字，使用默认值 1000ms")
            self.sampling_rate = 1000.0

    def set_max_voltage(self, max_voltage):
        """设置最大电压限制"""
        self.max_voltage = max_voltage
        print(f"设置最大电压限制为: {max_voltage}V")

    def set_warmup_time(self, warmup_time):
        """设置预热时间"""
        self.warmup_time = warmup_time
        print(f"设置预热时间为: {warmup_time}秒")

    def connect_sensor(self, port):
        """连接温度传感器"""
        try:
            print(f"正在连接温度传感器，串口: {port}")
            self.modbus_sensor = ModbusSensor(port)
            
            # 检查连接是否成功
            if not self.modbus_sensor.is_connected():
                print("温度传感器连接失败，请检查串口连接")
                return False
                
            # 测试读取温度
            print("测试读取温度...")
            temperature = self.modbus_sensor.read_temperature(2)  # 测试读取传感器2的温度
            if temperature is not None:
                print(f"温度传感器连接成功，测试读取温度: {temperature}°C")
                return True
            else:
                print("温度传感器连接成功，但读取温度失败")
                return False
                
        except Exception as e:
            print(f"连接传感器失败: {e}")
            print(f"错误类型: {type(e).__name__}")
            print(f"错误详情: {str(e)}")
            return False

    def connect_power_supply(self, port):
        """连接电源发生器"""
        try:
            self.power_supply = PowerSupply(port)
            return True
        except Exception as e:
            print(f"连接电源发生器失败: {e}")
            return False

    def start(self):
        """开始控制"""
        self.is_running = True
        self.is_paused = False
        self.last_error = 0.0
        self.integral = 0.0
        
        # 记录预热开始时间
        self.warmup_start_time = time.time()
        self.is_warmup = True  # 标记进入预热阶段
        
        # 设置初始电压并开启电源输出
        if self.power_supply:
            # 确保初始电压不超过最大电压
            initial_voltage = min(self.initial_voltage, self.max_voltage)
            
            # 重试设置电压
            voltage_set = False
            for _ in range(3):  # 最多重试3次
                try:
                    if self.power_supply.set_voltage(initial_voltage):
                        print(f"成功设置初始电压: {initial_voltage}V")
                        voltage_set = True
                    break
                except:
                    print("设置初始电压失败，重试中...")
                    time.sleep(0.5)
            
            if not voltage_set:
                print("设置初始电压失败，将继续运行但可能无法控制温度")
            
            # 等待电压设置完成
            time.sleep(0.1)
            
            # 重试开启输出
            output_on = False
            for _ in range(3):  # 最多重试3次
                try:
                    if self.power_supply.on_output():
                        print("成功开启电源输出")
                        output_on = True
                        break
                    else:
                        print("开启电源输出失败，重试中...")
                        time.sleep(0.5)
                except Exception as e:
                    print(f"开启电源输出时发生错误: {e}")
                    time.sleep(0.5)
            
            if not output_on:
                print("开启电源输出失败，将继续运行但可能无法控制温度")
            
            # 记录预热数据
            print(f"开始预热，等待 {self.warmup_time} 秒...")
            self.record_warmup_data(self.warmup_time)
            print("预热完成，开始PID控制")
            
            # 记录PID控制开始时间
            self.start_time = time.time()
            self.is_warmup = False  # 标记预热结束

    def record_warmup_data(self, duration):
        """记录预热数据"""
        print("\n=== 开始记录预热数据 ===")
        start_time = time.time()
        
        while time.time() - start_time < duration:
            try:
                # 记录当前时间
                current_time = time.time()
                elapsed_time = current_time - self.warmup_start_time
                
                # 记录时间数据
                self.warmup_time_data.append(elapsed_time)
                self.warmup_system_time_data.append(current_time)
                print(f"记录预热时间数据: elapsed={elapsed_time:.2f}s, system={current_time}")
                
                # 读取所有选中传感器的温度
                for sensor in self.selected_sensors:
                    try:
                        temperature = self.modbus_sensor.read_temperature(sensor)
                        if temperature is not None:
                            channel_key = f'channel_{sensor}'
                            if channel_key not in self.warmup_temperature_data:
                                self.warmup_temperature_data[channel_key] = []
                            self.warmup_temperature_data[channel_key].append(temperature)
                            print(f"记录预热传感器 {sensor} 温度: {temperature}°C")
                    except Exception as e:
                        print(f"读取预热传感器 {sensor} 温度失败: {e}")
                        continue
                
                # 读取主传感器的温度（如果存在且不在选中列表中）
                if self.main_sensor and self.main_sensor not in self.selected_sensors:
                    try:
                        temperature = self.modbus_sensor.read_temperature(self.main_sensor)
                        if temperature is not None:
                            channel_key = f'channel_{self.main_sensor}'
                            if channel_key not in self.warmup_temperature_data:
                                self.warmup_temperature_data[channel_key] = []
                            self.warmup_temperature_data[channel_key].append(temperature)
                            print(f"记录预热主传感器 {self.main_sensor} 温度: {temperature}°C")
                    except Exception as e:
                        print(f"读取预热主传感器 {self.main_sensor} 温度失败: {e}")
                
                # 读取电压和电流
                try:
                    voltage = self.power_supply.read_voltage()
                    if voltage is not None:
                        self.warmup_voltage_data.append(voltage)
                        print(f"记录预热电压: {voltage}V")
                    
                    current = self.power_supply.read_current()
                    if current is not None:
                        self.warmup_current_data.append(current)
                        print(f"记录预热电流: {current}A")
                except Exception as e:
                    print(f"读取预热电压或电流失败: {e}")
                
                # 等待采样间隔
                time.sleep(self.sampling_rate / 1000.0)
                
            except Exception as e:
                print(f"记录预热数据时发生错误: {e}")
                time.sleep(0.1)  # 发生错误时短暂等待
        
        print("=== 预热数据记录完成 ===\n")

    def pause(self):
        """暂停控制"""
        if self.is_running and not self.is_paused:
            if self.power_supply:
                self.power_supply.off_output()
            self.is_paused = True

    def resume(self):
        """恢复控制"""
        if self.is_running and self.is_paused:
            if self.power_supply:
                self.power_supply.on_output()
            self.is_paused = False

    def stop(self):
        """停止控制 - 具有最高优先级的安全停止功能"""
        print("\n=== 紧急停止控制 ===")
        
        # 立即设置状态标志，防止其他操作继续执行
        self.is_running = False
        self.is_paused = False
        self.is_warmup = False
        
        # 立即关闭电源输出（最高优先级）
        if self.power_supply:
            try:
                print("正在紧急关闭电源输出...")
                # 立即设置电压为0
                self.power_supply.set_voltage(0.0)
                # 关闭输出
                self.power_supply.off_output()
                print("电源输出已紧急关闭")
            except Exception as e:
                print(f"紧急关闭电源输出时发生错误: {e}")
                # 继续执行，确保其他清理操作也能完成
        
        # 关闭串口连接
        try:
            if self.power_supply:
                print("正在关闭电源发生器串口...")
                try:
                    self.power_supply.close()
                    print("电源发生器串口已关闭")
                except Exception as e:
                    print(f"关闭电源发生器串口时发生错误: {e}")
            
            if self.modbus_sensor:
                print("正在关闭温度传感器串口...")
                try:
                    self.modbus_sensor.close()
                    print("温度传感器串口已关闭")
                except Exception as e:
                    print(f"关闭温度传感器串口时发生错误: {e}")
        except Exception as e:
            print(f"关闭串口时发生错误: {e}")
        
        # 重置所有控制参数
        self.last_error = 0.0
        self.integral = 0.0
        self.in_dead_zone = False
        self.dead_zone_voltage = 0.0
        self.start_time = None
        self.warmup_start_time = None
        
        # 打印最终的数据状态
        print("\n=== 最终数据记录状态 ===")
        print("预热数据:")
        print(f"预热时间数据长度: {len(self.warmup_time_data)}")
        print(f"预热系统时间数据长度: {len(self.warmup_system_time_data)}")
        print(f"预热电压数据长度: {len(self.warmup_voltage_data)}")
        print(f"预热电流数据长度: {len(self.warmup_current_data)}")
        print(f"预热温度数据通道数: {len(self.warmup_temperature_data)}")
        for channel, temps in self.warmup_temperature_data.items():
            print(f"预热通道 {channel} 温度数据长度: {len(temps)}")
        
        print("\nPID控制数据:")
        print(f"时间数据长度: {len(self.time_data)}")
        print(f"系统时间数据长度: {len(self.system_time_data)}")
        print(f"电压数据长度: {len(self.voltage_data)}")
        print(f"电流数据长度: {len(self.current_data)}")
        print(f"温度数据通道数: {len(self.temperature_data)}")
        for channel, temps in self.temperature_data.items():
            print(f"通道 {channel} 温度数据长度: {len(temps)}")
        
        print("\n=== 控制已完全停止 ===\n")
        
        # 返回最终状态
        return True

    def update(self, current_temp):
        """更新PID控制"""
        # 首先检查是否处于停止状态，如果是则立即返回
        if not self.is_running:
            print("控制已停止，不执行更新")
            return
            
        print("\n=== PID控制器更新 ===")
        print(f"当前温度: {current_temp}°C")
        print(f"目标温度: {self.setpoint}°C")
        print(f"控制状态: running={self.is_running}, paused={self.is_paused}, warmup={self.is_warmup}")
        
        # 检查串口状态
        if not self.modbus_sensor or not self.power_supply:
            print("警告: 串口未连接")
            return

        # 检查串口是否实际打开
        try:
            if not self.modbus_sensor.is_open():
                print("警告: 温度传感器串口未打开，尝试重新连接...")
                if not self.connect_sensor(self.modbus_sensor.port):
                    print("重新连接温度传感器失败")
                    return
        except Exception as e:
            print(f"检查温度传感器串口状态失败: {e}")
            return

        try:
            if not self.power_supply.is_open():
                print("警告: 电源发生器串口未打开，尝试重新连接...")
                if not self.connect_power_supply(self.power_supply.port):
                    print("重新连接电源发生器失败")
                    return
        except Exception as e:
            print(f"检查电源发生器串口状态失败: {e}")
            return

        try:
            # 记录当前时间
            current_time = time.time()
            if self.start_time is None:
                self.start_time = current_time
            elapsed_time = current_time - self.start_time
            
            # 确保数据列表已初始化
            if not hasattr(self, 'time_data'):
                self.time_data = []
            if not hasattr(self, 'system_time_data'):
                self.system_time_data = []
            if not hasattr(self, 'voltage_data'):
                self.voltage_data = []
            if not hasattr(self, 'current_data'):
                self.current_data = []
            if not hasattr(self, 'temperature_data'):
                self.temperature_data = {}
            
            # 记录时间数据
            self.time_data.append(elapsed_time)
            self.system_time_data.append(current_time)
            print(f"记录时间数据: elapsed={elapsed_time:.2f}s, system={current_time}")

            # 如果是暂停状态，记录温度数据，但将电压和电流设为0
            if self.is_paused:
                print("控制已暂停，仅记录温度数据")
                # 记录电压和电流为0
                self.voltage_data.append(0.0)
                self.current_data.append(0.0)
                
                # 读取所有选中传感器的温度
                for sensor in self.selected_sensors:
                    try:
                        temperature = self.modbus_sensor.read_temperature(sensor)
                        if temperature is not None:
                            channel_key = f'channel_{sensor}'
                            if channel_key not in self.temperature_data:
                                self.temperature_data[channel_key] = []
                            self.temperature_data[channel_key].append(temperature)
                            print(f"记录传感器 {sensor} 温度: {temperature}°C")
                    except Exception as e:
                        print(f"读取传感器 {sensor} 温度失败: {e}")
                        continue

                # 读取主传感器的温度（如果存在且不在选中列表中）
                if self.main_sensor and self.main_sensor not in self.selected_sensors:
                    try:
                        temperature = self.modbus_sensor.read_temperature(self.main_sensor)
                        if temperature is not None:
                            channel_key = f'channel_{self.main_sensor}'
                            if channel_key not in self.temperature_data:
                                self.temperature_data[channel_key] = []
                            self.temperature_data[channel_key].append(temperature)
                            print(f"记录主传感器 {self.main_sensor} 温度: {temperature}°C")
                    except Exception as e:
                        print(f"读取主传感器 {self.main_sensor} 温度失败: {e}")
                return

            # 如果不是暂停状态，执行正常的PID控制逻辑
            # 计算误差
            error = self.setpoint - current_temp
            print(f"\n=== PID控制计算 ===")
            print(f"目标温度: {self.setpoint}°C")
            print(f"当前温度: {current_temp}°C")
            print(f"误差: {error}°C")
            
            # 检查是否进入死区
            if abs(error) <= self.dead_zone:
                if not self.in_dead_zone:
                    # 刚进入死区，记录当前电压
                    try:
                        self.dead_zone_voltage = self.power_supply.read_voltage()
                        if self.dead_zone_voltage is None or self.dead_zone_voltage < 1.0:
                            # 如果读取失败或电压太低，使用初始电压
                            self.dead_zone_voltage = min(self.initial_voltage, self.max_voltage)
                        print(f"进入死区，记录当前电压: {self.dead_zone_voltage}V")
                    except Exception as e:
                        print(f"读取死区电压失败: {e}")
                        # 如果读取失败，使用初始电压
                        self.dead_zone_voltage = min(self.initial_voltage, self.max_voltage)
                    self.in_dead_zone = True
                
                # 在死区内保持固定电压，但确保不超过最大电压
                pid_output = min(max(1.0, self.dead_zone_voltage), self.max_voltage)
                print(f"在死区内，使用固定电压: {pid_output}V")
            else:
                # 超出死区，使用PID控制
                if self.in_dead_zone:
                    print("超出死区，恢复PID控制")
                    self.in_dead_zone = False
                
                # 计算积分项
                integral_term = error * (self.sampling_rate / 1000.0)
                self.integral += integral_term
                # 限制积分项的范围，防止积分饱和
                self.integral = max(-200, min(200, self.integral))
                print(f"积分项: {integral_term}, 累计积分: {self.integral}")
                
                # 计算微分项
                derivative = (error - self.last_error) / (self.sampling_rate / 1000.0)
                # 限制微分项的变化率
                derivative = max(-200, min(200, derivative))
                print(f"微分项: {derivative}")
                
                # 计算PID输出
                p_term = self.kp * error
                i_term = self.ki * self.integral
                d_term = self.kd * derivative
                pid_output = p_term + i_term + d_term
                
                print(f"P项 ({self.kp} * {error}): {p_term}")
                print(f"I项 ({self.ki} * {self.integral}): {i_term}")
                print(f"D项 ({self.kd} * {derivative}): {d_term}")
                print(f"PID输出 (P + I + D): {pid_output}")
            
            # 限制输出范围在 1V 到最大电压之间
            pid_output = min(max(1.0, pid_output), self.max_voltage)
            print(f"限制后的PID输出: {pid_output}V")
            
            # 更新上一次误差
            self.last_error = error
            
            # 设置电源电压
            if self.power_supply:
                self.power_supply.set_voltage(pid_output)
                print(f"设置电源电压: {pid_output}V")
            
            # 读取所有选中传感器的温度
            temperatures = {}
            for sensor in self.selected_sensors:
                try:
                    temperature = self.modbus_sensor.read_temperature(sensor)
                    if temperature is not None:
                        temperatures[sensor] = temperature
                        channel_key = f'channel_{sensor}'
                        if channel_key not in self.temperature_data:
                            self.temperature_data[channel_key] = []
                        self.temperature_data[channel_key].append(temperature)
                        print(f"记录传感器 {sensor} 温度: {temperature}°C")
                except Exception as e:
                    print(f"读取传感器 {sensor} 温度失败: {e}")
                    continue

            # 读取主传感器的温度（如果存在且不在选中列表中）
            if self.main_sensor and self.main_sensor not in self.selected_sensors:
                try:
                    temperature = self.modbus_sensor.read_temperature(self.main_sensor)
                    if temperature is not None:
                        temperatures[self.main_sensor] = temperature
                        channel_key = f'channel_{self.main_sensor}'
                        if channel_key not in self.temperature_data:
                            self.temperature_data[channel_key] = []
                        self.temperature_data[channel_key].append(temperature)
                        print(f"记录主传感器 {self.main_sensor} 温度: {temperature}°C")
                except Exception as e:
                    print(f"读取主传感器 {self.main_sensor} 温度失败: {e}")

            # 读取电压和电流
            try:
                voltage = self.power_supply.read_voltage()
                if voltage is not None:
                    self.voltage_data.append(voltage)
                    print(f"记录电压: {voltage}V")
                
                current = self.power_supply.read_current()
                if current is not None:
                    self.current_data.append(current)
                    print(f"记录电流: {current}A")
            except Exception as e:
                print(f"读取电压或电流失败: {e}")

            # 更新当前温度（使用主传感器或第一个选中传感器的温度）
            if self.main_sensor and self.main_sensor in temperatures:
                self.current_temperature = temperatures[self.main_sensor]
            elif self.selected_sensors and self.selected_sensors[0] in temperatures:
                self.current_temperature = temperatures[self.selected_sensors[0]]
            else:
                self.current_temperature = None

            # 更新当前电压
            self.current_voltage = voltage
            print("=== PID控制计算完成 ===\n")

        except Exception as e:
            print(f"更新控制时发生错误: {e}")
            import traceback
            traceback.print_exc()

    def get_all_temperatures(self):
        """获取所有传感器的当前温度"""
        temperatures = {}
        
        # 从已记录的数据中获取温度
        for channel, temps in self.temperature_data.items():
            if temps:  # 确保有数据
                sensor = int(channel.split('_')[1])  # 从 channel_X 中提取传感器编号
                temperatures[sensor] = temps[-1]  # 获取最新的温度值
        
        return temperatures

    def get_recorded_data(self):
        """获取记录的数据"""
        # 确保所有数据列表已初始化
        if not hasattr(self, 'time_data'):
            self.time_data = []
        if not hasattr(self, 'system_time_data'):
            self.system_time_data = []
        if not hasattr(self, 'voltage_data'):
            self.voltage_data = []
        if not hasattr(self, 'current_data'):
            self.current_data = []
        if not hasattr(self, 'temperature_data'):
            self.temperature_data = {}
        
        # 打印数据长度信息
        print("\n=== 数据记录状态 ===")
        print("预热数据:")
        print(f"预热时间数据长度: {len(self.warmup_time_data)}")
        print(f"预热系统时间数据长度: {len(self.warmup_system_time_data)}")
        print(f"预热电压数据长度: {len(self.warmup_voltage_data)}")
        print(f"预热电流数据长度: {len(self.warmup_current_data)}")
        print(f"预热温度数据通道数: {len(self.warmup_temperature_data)}")
        for channel, temps in self.warmup_temperature_data.items():
            print(f"预热通道 {channel} 温度数据长度: {len(temps)}")
        
        print("\nPID控制数据:")
        print(f"时间数据长度: {len(self.time_data)}")
        print(f"系统时间数据长度: {len(self.system_time_data)}")
        print(f"电压数据长度: {len(self.voltage_data)}")
        print(f"电流数据长度: {len(self.current_data)}")
        print(f"温度数据通道数: {len(self.temperature_data)}")
        for channel, temps in self.temperature_data.items():
            print(f"通道 {channel} 温度数据长度: {len(temps)}")
        
        # 合并预热和PID控制数据
        data = {
            'time': self.warmup_time_data + self.time_data,
            'system_time': self.warmup_system_time_data + list(self.system_time_data),
            'voltage': self.warmup_voltage_data + self.voltage_data,
            'current': self.warmup_current_data + self.current_data,
            'temperatures': {}
        }
        
        # 合并温度数据
        all_channels = set(self.warmup_temperature_data.keys()) | set(self.temperature_data.keys())
        for channel in all_channels:
            warmup_temps = self.warmup_temperature_data.get(channel, [])
            control_temps = self.temperature_data.get(channel, [])
            data['temperatures'][channel] = warmup_temps + control_temps
        
        return data

    def set_selected_sensors(self, sensors, main_sensor=None):
        """设置选中的传感器列表和主传感器"""
        self.selected_sensors = sensors
        self.main_sensor = main_sensor
        
        # 获取所有当前需要的传感器
        all_sensors = set(sensors)
        if main_sensor is not None:
            all_sensors.add(main_sensor)
        
        # 清理不再需要的温度数据队列
        channels_to_remove = []
        for channel in self.temperature_data.keys():
            sensor_num = int(channel.split('_')[1])
            if sensor_num not in all_sensors:
                channels_to_remove.append(channel)
        
        for channel in channels_to_remove:
            del self.temperature_data[channel]
            print(f"移除传感器 {channel.split('_')[1]} 的温度数据队列")
        
        # 为所有需要的传感器初始化温度数据队列
        for sensor in all_sensors:
            channel_key = f'channel_{sensor}'
            if channel_key not in self.temperature_data:
                self.temperature_data[channel_key] = []  # 使用列表而不是deque
                print(f"初始化传感器 {sensor} 的温度数据队列")
        
        print(f"已设置选中的传感器: {sensors}, 主传感器: {main_sensor}")
        print(f"温度数据队列: {list(self.temperature_data.keys())}")

    def get_current_temperature(self):
        """获取主传感器的当前温度"""
        if self.main_sensor is not None:
            channel_key = f'channel_{self.main_sensor}'
            if channel_key in self.temperature_data and self.temperature_data[channel_key]:
                return self.temperature_data[channel_key][-1]
        return None

    def get_current_voltage(self):
        """获取当前电压"""
        if self.power_supply:
            try:
                voltage = self.power_supply.read_voltage()
                print(f"读取当前电压: {voltage}V")
                return voltage
            except Exception as e:
                print(f"读取电压失败: {e}")
                return None
        return None