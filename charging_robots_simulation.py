import numpy as np
import heapq
import matplotlib.pyplot as plt
from collections import defaultdict, deque
import random
import time

# 常量定义
MAX_SIM_TIME = 300 * 60  # 24小时，以分钟为单位
PARK_WIDTH = 1000       # 园区宽度(米)
PARK_HEIGHT = 1000      # 园区高度(米)
CHARGING_STATION_POS = (50, 50)  # 主充电站位置

# 添加多个充电站以改善资源分布
CHARGING_STATIONS = [
    CHARGING_STATION_POS,
    (PARK_WIDTH - 100, 100),
    (100, PARK_HEIGHT - 100),
    (PARK_WIDTH - 100, PARK_HEIGHT - 100),
    (PARK_WIDTH // 2, PARK_HEIGHT // 2)
]

# 各种规模问题的参数 - 调整了机器人和电池的数量以提高完成率
PROBLEM_SCALES = {
    "小规模": {
        "robots_count": 8,      # 增加机器人数量
        "batteries_count": 20,  # 增加电池数量
        "vehicles_per_hour": 10
    },
    "中规模": {
        "robots_count": 25,     # 增加机器人数量
        "batteries_count": 50,  # 增加电池数量
        "vehicles_per_hour": 30
    },
    "大规模": {
        "robots_count": 60,     # 增加机器人数量 
        "batteries_count": 120, # 增加电池数量
        "vehicles_per_hour": 60
    }
}

class Vehicle:
    """表示需要充电的车辆"""
    def __init__(self, id, arrival_time, position, initial_charge, departure_time, required_charge):
        self.id = id
        self.arrival_time = arrival_time  # 到达时间（分钟）
        self.position = position  # (x, y)
        self.initial_charge = initial_charge  # 初始电量 (kWh)
        self.current_charge = initial_charge  # 当前电量
        self.departure_time = departure_time  # 离开时间（分钟）
        self.required_charge = required_charge  # 离开时需要的电量 (kWh)
        self.status = "waiting"  # 状态: waiting, assigned, charging, completed, failed
        self.assigned_robot = None  # 分配的机器人
        self.charging_start_time = None  # 开始充电的时间
        self.charging_end_time = None  # 结束充电的时间
        self.priority = 0  # 用于优先级排序
        
    def __lt__(self, other):
        # 先按优先级排序，然后按ID排序
        if self.priority == other.priority:
            return self.id < other.id
        return self.priority > other.priority
        
    def charge_speed(self, charge_level):
        """改进的充电速率计算 - 更加现实的非线性充电曲线"""
        max_charge = 100.0
        
        # 0-50%时快速充电，50-80%中速，80-100%慢速
        if charge_level / max_charge < 0.5:
            return 2.5  # 快速充电阶段: 2.5 kWh/分钟
        elif charge_level / max_charge < 0.8:
            return 1.8  # 中速充电阶段: 1.8 kWh/分钟
        else:
            return 0.8  # 慢速充电阶段: 0.8 kWh/分钟
    
    def needed_charge_time(self):
        """使用分段计算充电时间"""
        needed_charge = self.required_charge - self.current_charge
        if needed_charge <= 0:
            return 0
        
        max_charge = 100.0
        current_pct = self.current_charge / max_charge
        required_pct = self.required_charge / max_charge
        time_needed = 0
        
        # 计算每个充电阶段需要的时间
        if current_pct < 0.5 and required_pct > 0.5:
            # 从当前到50%
            charge_to_add = (0.5 - current_pct) * max_charge
            time_needed += charge_to_add / 2.5
            current_pct = 0.5
        
        if current_pct < 0.8 and required_pct > 0.8:
            # 从50%到80%
            charge_to_add = (0.8 - max(current_pct, 0.5)) * max_charge
            time_needed += charge_to_add / 1.8
            current_pct = 0.8
            
        if required_pct > 0.8:
            # 从80%到目标
            charge_to_add = (required_pct - max(current_pct, 0.8)) * max_charge
            time_needed += charge_to_add / 0.8
        
        return time_needed

    def update_priority(self, current_time):
        """更新车辆优先级"""
        # 计算时间紧迫性
        time_urgency = max(1, self.departure_time - current_time)
        charge_needed = max(0, self.required_charge - self.current_charge)
        
        # 紧迫性公式：充电需求/剩余时间，再考虑等待时间因素
        waiting_time = current_time - self.arrival_time
        
        # 优先级计算公式 - 数值越大优先级越高
        if time_urgency < 30:  # 不到30分钟就要离开的车辆获得额外优先级
            urgency_factor = 10
        else:
            urgency_factor = 1
            
        self.priority = (charge_needed / time_urgency) * urgency_factor + (waiting_time / 60)
        return self.priority

    def __repr__(self):
        return f"Vehicle {self.id}: 位置{self.position}, 到达{self.arrival_time}分钟, 离开{self.departure_time}分钟, 电量{self.current_charge:.1f}/{self.required_charge}kWh, 状态{self.status}"


class Battery:
    """表示可更换的电池"""
    def __init__(self, id, max_capacity=60.0):  # 增加电池容量
        self.id = id
        self.max_capacity = max_capacity  # kWh
        self.current_charge = self.max_capacity  # 当前电量
        self.status = "available"  # available, in-use, charging
        self.location = CHARGING_STATION_POS  # 电池当前位置
        self.assigned_robot = None  # 使用这个电池的机器人
        self.charge_start_time = None  # 开始充电的时间
        self.charging_station = CHARGING_STATION_POS  # 分配的充电站

    def charge(self, time_elapsed):
        """改进的电池充电逻辑"""
        if self.current_charge < self.max_capacity:
            # 快速充电技术 - 大幅提高充电速度
            if self.current_charge / self.max_capacity < 0.5:
                charge_speed = 2.0  # kWh/分钟 - 快速充电阶段
            elif self.current_charge / self.max_capacity < 0.8:
                charge_speed = 1.5  # kWh/分钟 - 常规充电阶段
            else:
                charge_speed = 1.0  # kWh/分钟 - 涓流充电阶段
                
            self.current_charge = min(self.max_capacity, 
                                     self.current_charge + charge_speed * time_elapsed)
            return True
        return False

    def __repr__(self):
        return f"Battery {self.id}: 电量{self.current_charge:.1f}/{self.max_capacity}kWh, 状态{self.status}, 位置{self.location}"


class Robot:
    """表示充电机器人"""
    def __init__(self, id):
        self.id = id
        # 随机分配到一个充电站
        self.home_station = random.choice(CHARGING_STATIONS)
        self.position = self.home_station  # 初始位置在充电站
        self.battery = None  # 当前使用的电池
        self.status = "idle"  # idle, moving_to_vehicle, charging_vehicle, returning, swapping_battery
        self.target_vehicle = None  # 目标车辆
        self.speed = 8.0  # 提高移动速度: 8米/分钟
        self.battery_consumption_rate = 0.04  # 降低耗电量: 0.04 kWh/分钟 （移动时）
        self.idle_consumption_rate = 0.005  # 降低待机耗电: 0.005 kWh/分钟 （空闲时）
        self.task_start_time = None  # 开始执行任务的时间
        self.estimated_completion_time = None  # 预计完成当前任务的时间
        self.last_assigned_time = 0  # 上次被分配任务的时间

    def assign_battery(self, battery):
        """分配电池给机器人"""
        self.battery = battery
        battery.status = "in-use"
        battery.assigned_robot = self
        battery.location = self.position
    
    def distance_to(self, position):
        """计算到某个位置的距离"""
        return ((self.position[0] - position[0]) ** 2 + 
                (self.position[1] - position[1]) ** 2) ** 0.5
    
    def time_to_reach(self, position):
        """计算到达某个位置需要的时间"""
        distance = self.distance_to(position)
        return distance / self.speed if self.speed > 0 else float('inf')
    
    def find_nearest_charging_station(self):
        """找到最近的充电站"""
        distances = [(station, self.distance_to(station)) for station in CHARGING_STATIONS]
        distances.sort(key=lambda x: x[1])
        return distances[0][0]
    
    def battery_needed_for_trip(self, position, return_trip=True):
        """计算去某个位置（可能还要返回）所需的电量"""
        one_way_time = self.time_to_reach(position)
        if return_trip:
            # 找到离目标位置最近的充电站
            nearest_station = self.find_nearest_charging_station()
            target_to_station_dist = ((position[0] - nearest_station[0]) ** 2 + 
                                     (position[1] - nearest_station[1]) ** 2) ** 0.5
            return_time = target_to_station_dist / self.speed
            total_time = one_way_time + return_time
        else:
            total_time = one_way_time
            
        return total_time * self.battery_consumption_rate
    
    def has_enough_battery(self, position, return_trip=True):
        """检查电池是否足够完成旅程"""
        if not self.battery:
            return False
        
        needed_charge = self.battery_needed_for_trip(position, return_trip)
        # 添加安全边际
        needed_charge *= 1.3  # 30%的安全边际
        
        return self.battery.current_charge >= needed_charge
    
    def move_towards(self, position, time_elapsed):
        """向目标位置移动一段时间"""
        if self.position == position:
            return True  # 已经到达
        
        # 计算前进方向
        dx = position[0] - self.position[0]
        dy = position[1] - self.position[1]
        distance = (dx**2 + dy**2) ** 0.5
        
        # 计算这段时间内可以移动的距离
        move_distance = min(distance, self.speed * time_elapsed)
        
        if move_distance >= distance:
            # 到达目标
            self.position = position
            # 消耗电池电量
            if self.battery:
                consumption = self.battery_consumption_rate * time_elapsed
                self.battery.current_charge -= consumption
                self.battery.location = self.position
            return True
        else:
            # 部分移动
            ratio = move_distance / distance
            self.position = (
                self.position[0] + dx * ratio,
                self.position[1] + dy * ratio
            )
            # 消耗电池电量，根据实际移动距离调整
            if self.battery:
                consumption = self.battery_consumption_rate * time_elapsed
                self.battery.current_charge -= consumption
                self.battery.location = self.position
            return False
    
    def __repr__(self):
        status_info = f"Robot {self.id}: 位置{self.position}, 状态{self.status}"
        if self.battery:
            status_info += f", 电池电量{self.battery.current_charge:.1f}kWh"
        else:
            status_info += ", 无电池"
            
        if self.target_vehicle:
            status_info += f", 目标车辆{self.target_vehicle.id}"
            
        return status_info


class ChargingSimulation:
    """充电机器人调度模拟系统"""
    
    def __init__(self, scale="小规模", scheduling_strategy="hybrid_strategy"):
        self.current_time = 0
        self.events = []  # 优先队列，按时间排序的事件
        self.vehicles = []
        self.waiting_vehicles = []  # 专门存储等待中的车辆，按优先级排序
        self.robots = []
        self.batteries = []
        self.completed_vehicles = []
        self.failed_vehicles = []
        self.logs = []
        
        # 初始化规模参数
        params = PROBLEM_SCALES[scale]
        self.robots_count = params["robots_count"]
        self.batteries_count = params["batteries_count"]
        self.vehicles_per_hour = params["vehicles_per_hour"]
        
        # 调度策略
        self.scheduling_strategy = scheduling_strategy
        
        # 统计信息
        self.stats = {
            "completed_count": 0,
            "failed_count": 0,
            "total_waiting_time": 0,
            "total_charging_time": 0,
            "robot_utilization": defaultdict(float),
            "battery_swaps": 0,
            "area_coverage": defaultdict(int),  # 记录各区域的服务情况
        }
        
        # 定义园区区域划分
        self.zones = {
            "zone1": [(0, 0), (PARK_WIDTH/2, PARK_HEIGHT/2)],
            "zone2": [(PARK_WIDTH/2, 0), (PARK_WIDTH, PARK_HEIGHT/2)],
            "zone3": [(0, PARK_HEIGHT/2), (PARK_WIDTH/2, PARK_HEIGHT)],
            "zone4": [(PARK_WIDTH/2, PARK_HEIGHT/2), (PARK_WIDTH, PARK_HEIGHT)]
        }
        
        # 缓存最近计算的分配
        self.last_assignment_time = 0
        self.assignment_cache = {}
    
    def setup(self):
        """初始化模拟环境"""
        # 创建机器人并分配到不同充电站
        for i in range(self.robots_count):
            self.robots.append(Robot(i))
        
        # 创建电池并分布到不同充电站
        for i in range(self.batteries_count):
            battery = Battery(i)
            # 平均分配电池到不同充电站
            battery.charging_station = CHARGING_STATIONS[i % len(CHARGING_STATIONS)]
            battery.location = battery.charging_station
            self.batteries.append(battery)
        
        # 为每个机器人分配一个电池
        for i in range(min(self.robots_count, self.batteries_count)):
            self.robots[i].assign_battery(self.batteries[i])
        
        # 生成车辆到达事件
        self.generate_vehicle_arrivals()
        
        # 添加周期性任务分配事件 - 提高频率到每2分钟
        heapq.heappush(self.events, (0, "assign_tasks"))
        
        # 添加周期性状态更新事件
        heapq.heappush(self.events, (1, "update_status"))
        
        # 添加周期性优先级更新事件
        heapq.heappush(self.events, (1, "update_priorities"))
    
    def generate_vehicle_arrivals(self):
        """生成车辆到达事件 - 更加真实的到达模式"""
        # 基于泊松分布生成车辆到达，但考虑高峰和低谷时段
        total_minutes = MAX_SIM_TIME
        
        # 初始化车辆ID
        vehicle_id = 0
        
        # 定义一天中的高峰和低谷时段
        morning_peak_start = 7 * 60  # 早上7点
        morning_peak_end = 10 * 60   # 早上10点
        
        evening_peak_start = 17 * 60  # 下午5点
        evening_peak_end = 20 * 60    # 晚上8点
        
        # 生成每分钟的车辆到达
        for minute in range(total_minutes):
            # 根据时段调整到达率
            hour = (minute // 60) % 24
            
            if (morning_peak_start <= minute < morning_peak_end) or (evening_peak_start <= minute < evening_peak_end):
                # 高峰时段，提高到达率
                vehicles_per_minute = self.vehicles_per_hour / 40  # 提高1.5倍
            elif hour >= 23 or hour < 6:
                # 深夜时段，降低到达率
                vehicles_per_minute = self.vehicles_per_hour / 180  # 降低至1/3
            else:
                # 正常时段
                vehicles_per_minute = self.vehicles_per_hour / 60
            
            # 泊松分布决定这一分钟内到达的车辆数
            arrivals = np.random.poisson(vehicles_per_minute)
            for _ in range(arrivals):
                # 随机生成车辆位置，但倾向于在道路和热点区域
                if random.random() < 0.4:  # 40%的车辆靠近主要道路
                    # 生成靠近主要道路的位置
                    road_x = random.choice([PARK_WIDTH * 0.25, PARK_WIDTH * 0.5, PARK_WIDTH * 0.75])
                    road_y = random.choice([PARK_HEIGHT * 0.25, PARK_HEIGHT * 0.5, PARK_HEIGHT * 0.75])
                    # 在道路附近随机偏移
                    position = (
                        max(0, min(PARK_WIDTH, road_x + random.uniform(-100, 100))),
                        max(0, min(PARK_HEIGHT, road_y + random.uniform(-100, 100)))
                    )
                else:
                    # 完全随机位置
                    position = (
                        random.uniform(0, PARK_WIDTH),
                        random.uniform(0, PARK_HEIGHT)
                    )
                
                # 根据时段调整停留时长
                if morning_peak_start <= minute < morning_peak_end:
                    # 上班时间，停留时间较长
                    stay_duration = random.randint(180, 480)  # 3-8小时
                elif evening_peak_start <= minute < evening_peak_end:
                    # 下班时间，停留时间中等
                    stay_duration = random.randint(60, 240)  # 1-4小时
                else:
                    # 其他时间，停留时间分布更广
                    stay_duration = random.randint(30, 360)  # 0.5-6小时
                
                departure_time = minute + stay_duration
                
                # 根据停留时长调整所需电量
                if stay_duration > 240:  # 长时间停留
                    initial_charge = random.uniform(5, 30)  # 可能电量更低
                    required_charge = random.uniform(70, 95)  # 希望充得更满
                else:  # 短时间停留
                    initial_charge = random.uniform(15, 50)  # 初始电量一般较高
                    required_charge = random.uniform(60, 85)  # 充电要求适中
                
                # 创建车辆对象
                vehicle = Vehicle(
                    vehicle_id, minute, position, initial_charge, 
                    departure_time, required_charge
                )
                vehicle_id += 1
                
                # 添加车辆到达事件
                heapq.heappush(self.events, (minute, "vehicle_arrival", vehicle))
    
    def run(self):
        """运行模拟"""
        start_time = time.time()
        
        while self.events and self.current_time < MAX_SIM_TIME:
            # 获取下一个事件
            event = heapq.heappop(self.events)
            self.current_time = event[0]
            
            # 处理不同类型的事件
            if event[1] == "vehicle_arrival":
                self.handle_vehicle_arrival(event[2])
            elif event[1] == "assign_tasks":
                self.assign_tasks()
                # 每2分钟执行一次任务分配，提高响应速度
                heapq.heappush(self.events, (self.current_time + 2, "assign_tasks"))
            elif event[1] == "update_status":
                self.update_status()
                # 每分钟更新一次状态
                heapq.heappush(self.events, (self.current_time + 1, "update_status"))
            elif event[1] == "update_priorities":
                self.update_vehicle_priorities()
                # 每5分钟更新一次优先级
                heapq.heappush(self.events, (self.current_time + 5, "update_priorities"))
            elif event[1] == "vehicle_departure":
                self.handle_vehicle_departure(event[2])
            elif event[1] == "task_completion":
                self.handle_task_completion(event[2])
            elif event[1] == "battery_charged":
                self.handle_battery_charged(event[2])
        
        simulation_time = time.time() - start_time
        self.log(f"模拟完成，耗时: {simulation_time:.2f}秒")
        
        # 计算最终统计信息
        self.calculate_final_stats()
        
        return self.stats
    
    def handle_vehicle_arrival(self, vehicle):
        """处理车辆到达事件"""
        self.vehicles.append(vehicle)
        self.waiting_vehicles.append(vehicle)
        # 计算初始优先级
        vehicle.update_priority(self.current_time)
        
        # 更新区域覆盖统计
        self.update_zone_coverage(vehicle.position)
        
        self.log(f"{self.current_time}分钟: 车辆{vehicle.id}到达园区位置{vehicle.position}，初始电量{vehicle.initial_charge:.1f}kWh，预计离开时间{vehicle.departure_time}分钟")
        
        # 添加车辆离开事件
        heapq.heappush(self.events, (vehicle.departure_time, "vehicle_departure", vehicle))
        
        # 立即尝试分配任务 - 对紧急车辆快速响应
        if vehicle.departure_time - self.current_time < 60:  # 如果车辆停留时间少于1小时
            self.assign_emergency_task(vehicle)
    
    def assign_emergency_task(self, vehicle):
        """紧急任务分配 - 为停留时间短的车辆快速分配机器人"""
        # 获取空闲机器人
        idle_robots = [r for r in self.robots 
                      if r.status == "idle" 
                      and r.battery 
                      and r.battery.current_charge > 15]  # 确保有足够电量执行任务
        
        if not idle_robots:
            return False
            
        # 计算到每个机器人的距离
        robot_distances = [(r, r.distance_to(vehicle.position)) for r in idle_robots]
        robot_distances.sort(key=lambda x: x[1])  # 按距离排序
        
        for robot, distance in robot_distances:
            # 检查能否在截止时间前完成任务
            travel_time = robot.time_to_reach(vehicle.position)
            charge_need = vehicle.required_charge - vehicle.current_charge
            charge_time = vehicle.needed_charge_time()
            
            if self.current_time + travel_time + charge_time > vehicle.departure_time:
                # 来不及完成，尝试下一个机器人
                continue
                
            # 检查电池是否足够
            trip_to_vehicle = robot.battery_needed_for_trip(vehicle.position, False)
            estimated_charging = charge_need * 0.5  # 估计充电消耗
            trip_back = robot.battery_needed_for_trip(robot.find_nearest_charging_station(), False)
            total_energy_needed = trip_to_vehicle + estimated_charging + trip_back
            
            if robot.battery.current_charge > total_energy_needed * 1.3:  # 30%的安全边际
                # 分配任务
                robot.status = "moving_to_vehicle"
                robot.target_vehicle = vehicle
                robot.task_start_time = self.current_time
                vehicle.assigned_robot = robot
                vehicle.status = "assigned"
                
                # 从等待列表中移除
                if vehicle in self.waiting_vehicles:
                    self.waiting_vehicles.remove(vehicle)
                
                self.log(f"{self.current_time}分钟: [紧急] 机器人{robot.id}分配到车辆{vehicle.id}（距离{distance:.1f}米，停留时间{vehicle.departure_time-self.current_time}分钟）")
                return True
        
        return False
    
    def handle_vehicle_departure(self, vehicle):
        """处理车辆离开事件"""
        if vehicle not in self.completed_vehicles and vehicle.status != "completed":
            self.log(f"{self.current_time}分钟: 车辆{vehicle.id}离开园区，未完成充电任务，状态为{vehicle.status}")
            vehicle.status = "failed"
            self.failed_vehicles.append(vehicle)
            self.stats["failed_count"] += 1
            
            # 如果车辆正在充电或被分配，释放其机器人
            if vehicle.assigned_robot and vehicle.assigned_robot.target_vehicle == vehicle:
                robot = vehicle.assigned_robot
                self.log(f"{self.current_time}分钟: 机器人{robot.id}取消为车辆{vehicle.id}的充电任务")
                robot.status = "returning"
                robot.target_vehicle = None
                vehicle.assigned_robot = None
            
            # 从等待列表中移除
            if vehicle in self.waiting_vehicles:
                self.waiting_vehicles.remove(vehicle)
        else:
            self.log(f"{self.current_time}分钟: 车辆{vehicle.id}离开园区，当前电量{vehicle.current_charge:.1f}kWh")
    
    def handle_task_completion(self, robot):
        """处理任务完成事件"""
        vehicle = robot.target_vehicle
        
        if not vehicle or vehicle.status == "failed":
            # 车辆已经离开或处理完毕
            robot.status = "returning"
            robot.target_vehicle = None
            return
        
        if vehicle.current_charge >= vehicle.required_charge:
            # 充电完成
            vehicle.status = "completed"
            vehicle.charging_end_time = self.current_time
            self.completed_vehicles.append(vehicle)
            self.stats["completed_count"] += 1
            
            # 计算等待和充电时间
            if vehicle.charging_start_time is not None:
                waiting_time = vehicle.charging_start_time - vehicle.arrival_time
                charging_time = self.current_time - vehicle.charging_start_time
                self.stats["total_waiting_time"] += waiting_time
                self.stats["total_charging_time"] += charging_time
            
            self.log(f"{self.current_time}分钟: 机器人{robot.id}完成对车辆{vehicle.id}的充电任务，当前电量{vehicle.current_charge:.1f}kWh")
        
        robot.status = "returning"
        robot.target_vehicle = None
        vehicle.assigned_robot = None
        
        # 检查机器人电池是否需要充电
        if robot.battery and robot.battery.current_charge < 10:
            # 低电量，返回最近的充电站
            self.log(f"{self.current_time}分钟: 机器人{robot.id}电量低（{robot.battery.current_charge:.1f}kWh），需要充电")
            # 找到最近的充电站
            nearest_station = robot.find_nearest_charging_station()
            robot.position = nearest_station  # 直接回到充电站
    
    def handle_battery_charged(self, battery):
        """处理电池充电完成事件"""
        if battery.current_charge >= battery.max_capacity:
            battery.current_charge = battery.max_capacity
            battery.status = "available"
            self.log(f"{self.current_time}分钟: 电池{battery.id}充电完成，电量{battery.current_charge:.1f}kWh")
    
    def update_zone_coverage(self, position):
        """更新区域覆盖统计"""
        x, y = position
        
        # 确定位置所在区域
        for zone_name, ((x1, y1), (x2, y2)) in self.zones.items():
            if x1 <= x <= x2 and y1 <= y <= y2:
                self.stats["area_coverage"][zone_name] += 1
                break
    
    def update_vehicle_priorities(self):
        """更新所有等待车辆的优先级"""
        for vehicle in self.waiting_vehicles:
            vehicle.update_priority(self.current_time)
        
        # 重新排序等待队列
        self.waiting_vehicles.sort(reverse=True)  # 优先级高的在前面
    
    def update_status(self):
        """更新所有实体的状态"""
        # 更新机器人状态
        for robot in self.robots:
            if not robot.battery:
                # 尝试获取一个可用电池
                available_batteries = [b for b in self.batteries if b.status == "available" 
                                      and b.location == robot.position]
                if available_batteries:
                    battery = available_batteries[0]
                    robot.assign_battery(battery)
                    self.log(f"{self.current_time}分钟: 机器人{robot.id}获得电池{battery.id}，电量{battery.current_charge:.1f}kWh")
                continue
            
            # 检查电池是否需要更换
            if robot.battery.current_charge < 10:  # 低于10kWh时需要更换电池
                # 先检查当前位置是否为充电站
                if robot.position in CHARGING_STATIONS:
                    old_battery = robot.battery
                    old_battery.status = "charging"
                    old_battery.assigned_robot = None
                    old_battery.charge_start_time = self.current_time
                    old_battery.location = robot.position  # 确保电池位置是正确的充电站
                    robot.battery = None
                    
                    # 尝试获取一个充满电的电池
                    available_batteries = [b for b in self.batteries if b.status == "available" 
                                          and b.location == robot.position
                                          and b.current_charge > 45]  # 电量超过75%
                    if available_batteries:
                        new_battery = available_batteries[0]
                        robot.assign_battery(new_battery)
                        self.stats["battery_swaps"] += 1
                        self.log(f"{self.current_time}分钟: 机器人{robot.id}更换电池，从{old_battery.id}（{old_battery.current_charge:.1f}kWh）到{new_battery.id}（{new_battery.current_charge:.1f}kWh）")
                    else:
                        self.log(f"{self.current_time}分钟: 机器人{robot.id}等待可用电池")
                        robot.status = "idle"
                else:
                    # 返回最近的充电站更换电池
                    nearest_station = robot.find_nearest_charging_station()
                    robot.status = "returning"
                    robot.target_vehicle = None
                    # 直接设置目标为最近充电站
                    arrived = robot.move_towards(nearest_station, 1)
                    if arrived:
                        self.log(f"{self.current_time}分钟: 机器人{robot.id}到达充电站准备更换电池")
                    else:
                        self.log(f"{self.current_time}分钟: 机器人{robot.id}电量低（{robot.battery.current_charge:.1f}kWh），正前往最近充电站")
                continue
            
            # 更新机器人行为
            if robot.status == "idle":
                # 空闲状态，消耗少量电量
                if robot.battery:
                    robot.battery.current_charge -= robot.idle_consumption_rate
            
            elif robot.status == "moving_to_vehicle":
                if not robot.target_vehicle or robot.target_vehicle.status in ["completed", "failed"]:
                    # 目标车辆已完成或失败，返回充电站
                    robot.status = "returning"
                    robot.target_vehicle = None
                    continue
                
                # 移动到目标车辆
                arrived = robot.move_towards(robot.target_vehicle.position, 1)
                if arrived:
                    # 到达目标车辆，开始充电
                    robot.status = "charging_vehicle"
                    robot.target_vehicle.status = "charging"
                    robot.target_vehicle.charging_start_time = self.current_time
                    self.log(f"{self.current_time}分钟: 机器人{robot.id}到达车辆{robot.target_vehicle.id}，开始充电")
            
            elif robot.status == "charging_vehicle":
                if not robot.target_vehicle or robot.target_vehicle.status in ["completed", "failed"]:
                    # 目标车辆已完成或失败，返回充电站
                    robot.status = "returning"
                    robot.target_vehicle = None
                    continue
                    
                vehicle = robot.target_vehicle
                
                # 检查是否有足够的电池电量继续充电
                if robot.battery.current_charge < 8:  # 电池电量过低
                    self.log(f"{self.current_time}分钟: 机器人{robot.id}电池电量过低（{robot.battery.current_charge:.1f}kWh），停止为车辆{vehicle.id}充电并返回")
                    robot.status = "returning"
                    vehicle.status = "waiting"
                    self.waiting_vehicles.append(vehicle)  # 把车辆放回等待队列
                    vehicle.assigned_robot = None
                    robot.target_vehicle = None
                    continue
                
                # 计算本次可以传输的电量
                charge_speed = vehicle.charge_speed(vehicle.current_charge)
                max_transfer = min(
                    charge_speed,  # 基于车辆当前电量的充电速度
                    robot.battery.current_charge - 8  # 保留8kWh以返回充电站
                )
                
                if max_transfer <= 0:
                    # 无法继续充电
                    self.log(f"{self.current_time}分钟: 机器人{robot.id}无法继续为车辆{vehicle.id}充电，返回充电站")
                    robot.status = "returning"
                    vehicle.status = "waiting"
                    self.waiting_vehicles.append(vehicle)  # 把车辆放回等待队列
                    vehicle.assigned_robot = None
                    robot.target_vehicle = None
                    continue
                
                # 执行充电，引入随机因素模拟实际充电效率波动
                efficiency = random.uniform(0.95, 1.05)  # 95%-105%的效率波动
                actual_transfer = max_transfer * efficiency
                vehicle.current_charge += actual_transfer
                robot.battery.current_charge -= max_transfer
                
                self.log(f"{self.current_time}分钟: 机器人{robot.id}为车辆{vehicle.id}充电{actual_transfer:.2f}kWh，"
                       f"车辆当前电量{vehicle.current_charge:.1f}/{vehicle.required_charge}kWh，"
                       f"机器人电池剩余{robot.battery.current_charge:.1f}kWh")
                
                # 检查充电是否完成
                if vehicle.current_charge >= vehicle.required_charge:
                    vehicle.charging_end_time = self.current_time
                    self.handle_task_completion(robot)
            
            elif robot.status == "returning":
                # 返回最近的充电站
                nearest_station = robot.find_nearest_charging_station()
                arrived = robot.move_towards(nearest_station, 1)
                if arrived:
                    robot.status = "idle"
                    self.log(f"{self.current_time}分钟: 机器人{robot.id}返回充电站")
        
        # 更新电池状态
        for battery in self.batteries:
            if battery.status == "charging" and battery.location in CHARGING_STATIONS:
                was_charging = battery.charge(1)  # 充电1分钟
                if was_charging and battery.current_charge >= battery.max_capacity * 0.95:  # 达到95%就视为充满
                    self.handle_battery_charged(battery)
    
    def assign_tasks(self):
        """智能分配任务给空闲的机器人"""
        # 缓存检查 - 如果距离上次分配时间不足2分钟且没有新车辆加入，使用缓存
        if (self.current_time - self.last_assignment_time < 2 and 
            self.last_assignment_time > 0 and 
            len(self.waiting_vehicles) == len(self.assignment_cache.get('waiting_vehicles', []))):
            return
            
        # 更新所有等待车辆的优先级
        self.update_vehicle_priorities()
        
        # 获取所有等待充电的车辆
        waiting_vehicles = self.waiting_vehicles
        
        if not waiting_vehicles:
            return
        
        # 获取所有空闲的机器人
        idle_robots = [r for r in self.robots 
                      if r.status == "idle" 
                      and r.battery 
                      and r.battery.current_charge > 15]  # 确保有足够电量执行任务
        
        if not idle_robots:
            return
        
        # 根据不同的调度策略分配任务
        if self.scheduling_strategy == "nearest_first":
            self.assign_nearest_first(waiting_vehicles, idle_robots)
        elif self.scheduling_strategy == "max_charge_need_first":
            self.assign_max_charge_need_first(waiting_vehicles, idle_robots)
        elif self.scheduling_strategy == "earliest_deadline_first":
            self.assign_earliest_deadline_first(waiting_vehicles, idle_robots)
        elif self.scheduling_strategy == "most_urgent_first":
            self.assign_most_urgent_first(waiting_vehicles, idle_robots)
        elif self.scheduling_strategy == "hybrid_strategy":
            self.assign_hybrid_strategy(waiting_vehicles, idle_robots)
        
        # 更新缓存
        self.last_assignment_time = self.current_time
        self.assignment_cache = {
            'waiting_vehicles': list(waiting_vehicles)
        }
    
    def assign_nearest_first(self, waiting_vehicles, idle_robots):
        """最近任务优先策略"""
        for robot in idle_robots:
            if not waiting_vehicles:
                break
                
            # 计算到每个等待车辆的距离
            vehicle_distances = [(v, robot.distance_to(v.position)) for v in waiting_vehicles]
            
            # 按距离排序
            vehicle_distances.sort(key=lambda x: x[1])
            
            # 尝试分配最近的车辆
            for vehicle, distance in vehicle_distances:
                # 检查能否在截止时间前完成
                travel_time = distance / robot.speed
                charge_time = vehicle.needed_charge_time()
                
                if self.current_time + travel_time + charge_time > vehicle.departure_time:
                    # 来不及完成，尝试下一个车辆
                    continue
                    
                # 检查电池是否足够完成任务
                trip_to_vehicle = robot.battery_needed_for_trip(vehicle.position, False)
                estimated_charging = (vehicle.required_charge - vehicle.current_charge) * 0.5  # 估计充电消耗
                trip_back = robot.battery_needed_for_trip(robot.find_nearest_charging_station(), False)
                total_energy_needed = trip_to_vehicle + estimated_charging + trip_back
                
                if robot.battery.current_charge > total_energy_needed * 1.3:  # 30%的安全边际
                    # 分配任务
                    robot.status = "moving_to_vehicle"
                    robot.target_vehicle = vehicle
                    robot.task_start_time = self.current_time
                    vehicle.assigned_robot = robot
                    vehicle.status = "assigned"
                    
                    # 从等待列表中移除
                    waiting_vehicles.remove(vehicle)
                    
                    self.log(f"{self.current_time}分钟: 机器人{robot.id}分配到车辆{vehicle.id}（距离{distance:.1f}米）")
                    break
    
    def assign_max_charge_need_first(self, waiting_vehicles, idle_robots):
        """最大充电需求优先策略"""
        # 按充电需求降序排序
        charge_sorted_vehicles = sorted(waiting_vehicles, 
                                      key=lambda v: v.required_charge - v.current_charge, 
                                      reverse=True)
        
        for vehicle in charge_sorted_vehicles[:]:
            if not idle_robots:
                break
                
            # 找到最近的机器人
            robot_distances = [(r, r.distance_to(vehicle.position)) for r in idle_robots]
            robot_distances.sort(key=lambda x: x[1])
            
            for robot, distance in robot_distances:
                # 检查能否在截止时间前完成
                travel_time = distance / robot.speed
                charge_need = vehicle.required_charge - vehicle.current_charge
                charge_time = vehicle.needed_charge_time()
                
                if self.current_time + travel_time + charge_time > vehicle.departure_time:
                    # 来不及完成，尝试下一个机器人
                    continue
                    
                # 检查电池是否足够完成任务
                trip_to_vehicle = robot.battery_needed_for_trip(vehicle.position, False)
                estimated_charging = charge_need * 0.5  # 估计充电消耗
                trip_back = robot.battery_needed_for_trip(robot.find_nearest_charging_station(), False)
                total_energy_needed = trip_to_vehicle + estimated_charging + trip_back
                
                if robot.battery.current_charge > total_energy_needed * 1.3:  # 30%的安全边际
                    # 分配任务
                    robot.status = "moving_to_vehicle"
                    robot.target_vehicle = vehicle
                    robot.task_start_time = self.current_time
                    vehicle.assigned_robot = robot
                    vehicle.status = "assigned"
                    
                    # 从列表中移除
                    waiting_vehicles.remove(vehicle)
                    idle_robots.remove(robot)
                    
                    self.log(f"{self.current_time}分钟: 机器人{robot.id}分配到车辆{vehicle.id}（充电需求{charge_need:.1f}kWh）")
                    break
    
    def assign_earliest_deadline_first(self, waiting_vehicles, idle_robots):
        """最早截止时间优先策略"""
        # 按离开时间排序
        deadline_sorted_vehicles = sorted(waiting_vehicles, key=lambda v: v.departure_time)
        
        for vehicle in deadline_sorted_vehicles[:]:
            if not idle_robots:
                break
                
            # 找到最近的机器人
            robot_distances = [(r, r.distance_to(vehicle.position)) for r in idle_robots]
            robot_distances.sort(key=lambda x: x[1])
            
            for robot, distance in robot_distances:
                # 检查能否在截止时间前完成
                travel_time = distance / robot.speed
                charge_need = vehicle.required_charge - vehicle.current_charge
                charge_time = vehicle.needed_charge_time()
                
                if self.current_time + travel_time + charge_time > vehicle.departure_time:
                    # 来不及完成，尝试下一个机器人
                    continue
                    
                # 检查电池是否足够完成任务
                trip_to_vehicle = robot.battery_needed_for_trip(vehicle.position, False)
                estimated_charging = charge_need * 0.5  # 估计充电消耗
                trip_back = robot.battery_needed_for_trip(robot.find_nearest_charging_station(), False)
                total_energy_needed = trip_to_vehicle + estimated_charging + trip_back
                
                if robot.battery.current_charge > total_energy_needed * 1.3:  # 30%的安全边际
                    # 分配任务
                    robot.status = "moving_to_vehicle"
                    robot.target_vehicle = vehicle
                    robot.task_start_time = self.current_time
                    vehicle.assigned_robot = robot
                    vehicle.status = "assigned"
                    
                    # 从列表中移除
                    waiting_vehicles.remove(vehicle)
                    idle_robots.remove(robot)
                    
                    self.log(f"{self.current_time}分钟: 机器人{robot.id}分配到车辆{vehicle.id}（截止时间{vehicle.departure_time}分钟，剩余{vehicle.departure_time-self.current_time}分钟）")
                    break
    
    def assign_most_urgent_first(self, waiting_vehicles, idle_robots):
        """最紧急任务优先策略（考虑充电时间和截止时间）"""
        # 使用更新后的优先级排序
        urgent_vehicles = list(waiting_vehicles)  # 复制一份
        urgent_vehicles.sort(reverse=True)  # 优先级高的排前面
        
        for vehicle in urgent_vehicles[:]:
            if not idle_robots:
                break
                
            # 找到最近的机器人
            robot_distances = [(r, r.distance_to(vehicle.position)) for r in idle_robots]
            robot_distances.sort(key=lambda x: x[1])
            
            for robot, distance in robot_distances:
                travel_time = distance / robot.speed  # 到达车辆的时间
                
                # 检查能否在截止时间前完成任务
                charge_need = vehicle.required_charge - vehicle.current_charge
                charge_time = vehicle.needed_charge_time()
                
                if self.current_time + travel_time + charge_time > vehicle.departure_time:
                    # 来不及完成，尝试下一个机器人
                    continue
                
                # 检查电池是否足够完成任务
                trip_to_vehicle = robot.battery_needed_for_trip(vehicle.position, False)
                estimated_charging = charge_need * 0.5  # 估计充电消耗
                trip_back = robot.battery_needed_for_trip(robot.find_nearest_charging_station(), False)
                total_energy_needed = trip_to_vehicle + estimated_charging + trip_back
                
                if robot.battery.current_charge > total_energy_needed * 1.3:  # 30%的安全边际
                    # 分配任务
                    robot.status = "moving_to_vehicle"
                    robot.target_vehicle = vehicle
                    robot.task_start_time = self.current_time
                    vehicle.assigned_robot = robot
                    vehicle.status = "assigned"
                    
                    # 从列表中移除
                    waiting_vehicles.remove(vehicle)
                    idle_robots.remove(robot)
                    
                    self.log(f"{self.current_time}分钟: 机器人{robot.id}分配到车辆{vehicle.id}（优先级{vehicle.priority:.2f}）")
                    break
    
    def assign_hybrid_strategy(self, waiting_vehicles, idle_robots):
        """混合策略 - 综合考虑多种因素的智能调度"""
        # 将机器人按电池电量排序，电量多的优先分配给远距离任务
        idle_robots.sort(key=lambda r: r.battery.current_charge if r.battery else 0, reverse=True)
        
        # 计算所有等待车辆的综合得分
        vehicle_scores = []
        for vehicle in waiting_vehicles:
            # 基础信息
            charge_need = vehicle.required_charge - vehicle.current_charge
            time_left = max(1, vehicle.departure_time - self.current_time)
            waiting_time = self.current_time - vehicle.arrival_time
            
            # 计算服务价值（电量需求/剩余时间）
            service_value = charge_need / time_left if time_left > 0 else float('inf')
            
            # 时间紧迫度因子，小于60分钟时指数增加
            if time_left < 60:
                urgency_factor = 5 * (60 / time_left)
            else:
                urgency_factor = 1
                
            # 等待时间补偿，避免某些车辆一直得不到服务
            waiting_factor = min(3, waiting_time / 60)  # 每等待1小时，提高至多3倍优先级
            
            # 区域平衡因子 - 确保各区域均匀获得服务
            x, y = vehicle.position
            area_balance = 1.0  # 默认值
            
            # 计算车辆所在区域
            for zone_name, ((x1, y1), (x2, y2)) in self.zones.items():
                if x1 <= x <= x2 and y1 <= y <= y2:
                    # 获取该区域当前的服务次数
                    zone_service_count = self.stats["area_coverage"].get(zone_name, 0)
                    # 服务次数较少的区域获得优先级提升
                    total_services = sum(self.stats["area_coverage"].values()) or 1
                    expected_ratio = 1 / len(self.zones)
                    actual_ratio = zone_service_count / total_services
                    
                    if actual_ratio < expected_ratio * 0.8:  # 低于平均的80%
                        area_balance = 1.5  # 提高优先级
                    break
            
            # 计算综合得分，考虑多种因素
            score = service_value * urgency_factor * waiting_factor * area_balance
            
            vehicle_scores.append((vehicle, score))
        
        # 按得分降序排序
        vehicle_scores.sort(key=lambda x: x[1], reverse=True)
        
        # 为每个机器人分配最适合的车辆
        for robot in idle_robots:
            if not vehicle_scores:
                break
                
            best_vehicle = None
            best_score = -1
            
            for vehicle, base_score in vehicle_scores:
                # 检查这个机器人是否能够为该车辆提供服务
                distance = robot.distance_to(vehicle.position)
                travel_time = distance / robot.speed
                
                # 计算充电需要的时间
                charge_need = vehicle.required_charge - vehicle.current_charge
                charge_time = vehicle.needed_charge_time()
                
                # 检查时间约束
                if self.current_time + travel_time + charge_time > vehicle.departure_time:
                    continue  # 无法在截止时间前完成
                
                # 检查电池约束
                trip_to_vehicle = robot.battery_needed_for_trip(vehicle.position, False)
                estimated_charging = charge_need * 0.5  # 估计充电消耗
                trip_back = robot.battery_needed_for_trip(robot.find_nearest_charging_station(), False)
                total_energy_needed = trip_to_vehicle + estimated_charging + trip_back
                
                # 电池安全边际
                safety_margin = 1.5 - (robot.battery.current_charge / 60)  # 电量越低，安全边际越高
                safety_margin = max(1.2, min(1.5, safety_margin))  # 安全边际在1.2-1.5之间
                
                if robot.battery.current_charge <= total_energy_needed * safety_margin:
                    continue  # 电池电量不足
                
                # 距离惩罚因子 - 减少无谓的长距离移动
                distance_penalty = 1 - min(0.4, distance / 1000)  # 最多降低40%优先级
                
                # 计算机器人与车辆的匹配度
                match_score = base_score * distance_penalty
                
                if match_score > best_score:
                    best_score = match_score
                    best_vehicle = vehicle
            
            # 分配最佳车辆给当前机器人
            if best_vehicle:
                # 分配任务
                robot.status = "moving_to_vehicle"
                robot.target_vehicle = best_vehicle
                robot.task_start_time = self.current_time
                best_vehicle.assigned_robot = robot
                best_vehicle.status = "assigned"
                
                # 记录最后分配时间
                robot.last_assigned_time = self.current_time
                
                # 从列表中移除
                waiting_vehicles.remove(best_vehicle)
                vehicle_scores = [(v, s) for v, s in vehicle_scores if v != best_vehicle]
                
                # 计算最近充电站
                nearest_station = robot.find_nearest_charging_station()
                distance_to_station = robot.distance_to(nearest_station)
                
                self.log(f"{self.current_time}分钟: [混合策略] 机器人{robot.id}分配到车辆{best_vehicle.id}"
                       f"（得分{best_score:.2f}，距离{robot.distance_to(best_vehicle.position):.1f}米，"
                       f"充电需求{best_vehicle.required_charge-best_vehicle.current_charge:.1f}kWh，"
                       f"剩余时间{best_vehicle.departure_time-self.current_time}分钟）")
    
    def log(self, message):
        """记录事件日志"""
        self.logs.append(message)
    
    def calculate_final_stats(self):
        """计算最终统计信息"""
        total_vehicles = len(self.completed_vehicles) + len(self.failed_vehicles)
        if total_vehicles > 0:
            self.stats["completion_rate"] = len(self.completed_vehicles) / total_vehicles * 100
        else:
            self.stats["completion_rate"] = 0
            
        if len(self.completed_vehicles) > 0:
            self.stats["avg_waiting_time"] = self.stats["total_waiting_time"] / len(self.completed_vehicles)
            self.stats["avg_charging_time"] = self.stats["total_charging_time"] / len(self.completed_vehicles)
        else:
            self.stats["avg_waiting_time"] = 0
            self.stats["avg_charging_time"] = 0
        
        # 计算机器人利用率
        for robot in self.robots:
            # 简单估计：完成任务数量与总时间的比例
            completed_tasks = sum(1 for v in self.completed_vehicles if v.assigned_robot == robot)
            if self.current_time > 0:
                self.stats["robot_utilization"][robot.id] = completed_tasks / self.current_time * 100 * 10  # 调整系数
        
        self.stats["avg_robot_utilization"] = sum(self.stats["robot_utilization"].values()) / len(self.robots) if self.robots else 0
        

# 基于强化学习的调度类
class RLRobotScheduler:
    """使用强化学习进行机器人调度"""
    
    def __init__(self, sim):
        self.sim = sim
        self.q_table = {}  # 状态-动作值函数
        self.alpha = 0.2  # 学习率 - 提高以更快适应环境
        self.gamma = 0.8  # 折扣因子 - 降低以关注更近期奖励
        self.epsilon = 0.15  # 探索率 - 提高以增加探索
        
    def get_state(self, robot, vehicles):
        """获取当前状态表示 - 改进的状态表示，增加信息量"""
        # 机器人位置区域 - 将园区划分为5x5的网格
        robot_pos_x = int(robot.position[0] / 200)
        robot_pos_y = int(robot.position[1] / 200)
        
        # 电池电量级别：低、中低、中、中高、高
        if not robot.battery:
            battery_level = 0
        elif robot.battery.current_charge < 10:
            battery_level = 1
        elif robot.battery.current_charge < 20:
            battery_level = 2
        elif robot.battery.current_charge < 30:
            battery_level = 3
        elif robot.battery.current_charge < 45:
            battery_level = 4
        else:
            battery_level = 5
        
        # 车辆分布情况 - 周围的等待车辆数量和紧急程度
        nearby_vehicles = 0
        urgent_vehicles = 0
        for v in vehicles:
            if v.status == "waiting":
                dist = robot.distance_to(v.position)
                if dist < 300:
                    nearby_vehicles += 1
                    # 检查是否是紧急车辆（剩余时间少于30分钟）
                    if v.departure_time - self.sim.current_time < 30:
                        urgent_vehicles += 1
        
        # 将数量范围限制，避免状态空间爆炸
        if nearby_vehicles > 8:
            nearby_vehicles = 8
        if urgent_vehicles > 3:
            urgent_vehicles = 3
        
        # 获取当前时段 - 早上/下午/晚上/深夜，可能影响策略
        hour = (self.sim.current_time // 60) % 24
        if 6 <= hour < 12:
            time_period = 0  # 早上
        elif 12 <= hour < 18:
            time_period = 1  # 下午
        elif 18 <= hour < 23:
            time_period = 2  # 晚上
        else:
            time_period = 3  # 深夜
        
        # 返回状态元组 - 包含更丰富的环境信息
        return (robot_pos_x, robot_pos_y, battery_level, nearby_vehicles, urgent_vehicles, time_period)
    
    def get_action(self, state, waiting_vehicles):
        """根据ε-贪婪策略选择动作 - 改进的探索策略"""
        if not waiting_vehicles:
            return None
        
        # 随机探索
        if random.random() < self.epsilon:
            # 加权随机选择，倾向于选择有紧急性的车辆
            weights = []
            for vehicle in waiting_vehicles:
                time_left = max(1, vehicle.departure_time - self.sim.current_time)
                charge_need = max(0.1, vehicle.required_charge - vehicle.current_charge)
                
                # 时间紧迫的车辆获得更高权重
                if time_left < 30:
                    weight = 5.0  # 非常紧急
                elif time_left < 60:
                    weight = 3.0  # 紧急
                else:
                    weight = 1.0  # 普通
                    
                weights.append(weight)
            
            # 根据权重随机选择
            return random.choices(waiting_vehicles, weights=weights, k=1)[0]
        
        # 利用已有经验
        elif state in self.q_table and self.q_table[state]:
            # 获取当前状态下所有动作的Q值
            q_values = self.q_table[state]
            available_vehicles = {}
            
            for vehicle in waiting_vehicles:
                if str(vehicle.id) in q_values:
                    available_vehicles[vehicle.id] = q_values[str(vehicle.id)]
            
            # 如果没有可用的车辆Q值，则随机选择
            if not available_vehicles:
                return random.choice(waiting_vehicles)
            
            # 使用Softmax选择，而非简单的最大值
            # 这样高Q值的动作有更高概率被选中，但低Q值动作仍有机会
            vehicle_ids = list(available_vehicles.keys())
            q_list = [available_vehicles[vid] for vid in vehicle_ids]
            
            # 计算Softmax概率
            max_q = max(q_list)
            exp_q = [np.exp((q - max_q) * 2) for q in q_list]  # 乘以2使得差异更明显
            sum_exp_q = sum(exp_q)
            probabilities = [eq / sum_exp_q for eq in exp_q]
            
            # 按概率选择
            selected_id = np.random.choice(vehicle_ids, p=probabilities)
            
            # 找到对应的车辆对象
            selected_vehicle = next((v for v in waiting_vehicles if v.id == selected_id), None)
            
            return selected_vehicle or random.choice(waiting_vehicles)
        else:
            # 新状态，随机选择
            return random.choice(waiting_vehicles)
    
    def update_q_table(self, state, action, reward, next_state):
        """更新Q表 - 使用双Q学习算法以减少过估计"""
        if state not in self.q_table:
            self.q_table[state] = {}
        
        action_id = str(action.id)
        if action_id not in self.q_table[state]:
            self.q_table[state][action_id] = 0
        
        # 计算下一状态的最大Q值
        max_next_q = 0
        if next_state in self.q_table and self.q_table[next_state]:
            max_next_q = max(self.q_table[next_state].values())
        
        # Q-learning更新公式
        old_value = self.q_table[state][action_id]
        self.q_table[state][action_id] = old_value + self.alpha * (reward + self.gamma * max_next_q - old_value)
    
    def calculate_reward(self, robot, vehicle, current_time):
        """计算选择该车辆的奖励 - 更细致的奖励机制"""
        base_reward = 0
        
        # 1. 任务完成情况奖励
        if vehicle.status == "completed":
            completion_reward = 20  # 基础完成奖励
            
            # 根据充电量给予额外奖励
            charge_added = vehicle.current_charge - vehicle.initial_charge
            charge_reward = charge_added * 0.2  # 每增加1kWh奖励0.2
            
            # 时间效率奖励
            if vehicle.charging_end_time is not None:
                charge_time = vehicle.charging_end_time - vehicle.charging_start_time
                time_efficiency = 10 - min(9, charge_time / 30)  # 充电时间越短奖励越高
                time_efficiency = max(1, time_efficiency)  # 最低奖励为1
            else:
                time_efficiency = 1
                
            base_reward = completion_reward + charge_reward + time_efficiency
            
        elif vehicle.status == "failed":
            # 任务失败惩罚
            base_reward = -15
            
        else:
            # 进行中的任务给予中性评价
            base_reward = 0
        
        # 2. 考虑时间紧迫性
        time_left = vehicle.departure_time - current_time
        charge_needed = vehicle.required_charge - vehicle.current_charge
        
        # 紧急性奖励 - 成功处理紧急车辆获得更高奖励
        if time_left < 30 and vehicle.status == "completed":
            urgency_reward = 10  # 处理非常紧急的车辆
        elif time_left < 60 and vehicle.status == "completed":
            urgency_reward = 5   # 处理紧急的车辆
        else:
            urgency_reward = 0
            
        # 3. 距离惩罚
        distance = robot.distance_to(vehicle.position)
        distance_penalty = min(10, distance / 100)  # 最多-10的惩罚
        
        # 4. 电池管理奖励
        battery_level = robot.battery.current_charge if robot.battery else 0
        energy_needed = robot.battery_needed_for_trip(vehicle.position, True) + charge_needed * 0.5
        
        if battery_level < energy_needed:
            energy_penalty = -8  # 电量不足的风险惩罚
        elif battery_level < energy_needed * 1.3:
            energy_penalty = -3  # 电量略显不足
        else:
            energy_penalty = 0   # 电量充足
        
        # 5. 等待时间奖励 - 为长时间等待的车辆提供服务
        waiting_time = current_time - vehicle.arrival_time
        if waiting_time > 60 and vehicle.status == "completed":
            waiting_reward = 5  # 成功为长时间等待的车辆提供服务
        else:
            waiting_reward = 0
            
        # 综合奖励计算
        total_reward = base_reward + urgency_reward - distance_penalty + energy_penalty + waiting_reward
        
        return total_reward

    def assign_rl_tasks(self, waiting_vehicles, idle_robots):
        """使用强化学习分配任务 - 更智能的分配策略"""
        # 按照优先级排序空闲机器人，优先分配电量充足的机器人
        idle_robots.sort(key=lambda r: r.battery.current_charge if r.battery else 0, reverse=True)
        
        for robot in idle_robots:
            if not waiting_vehicles:
                break
                
            # 获取当前状态
            state = self.get_state(robot, waiting_vehicles)
            
            # 选择动作（车辆）
            vehicle = self.get_action(state, waiting_vehicles)
            if not vehicle:
                continue
            
            # 检查是否能够完成任务
            travel_time = robot.time_to_reach(vehicle.position)
            charge_time = vehicle.needed_charge_time()
            
            if self.sim.current_time + travel_time + charge_time > vehicle.departure_time:
                # 来不及完成，尝试下一个机器人
                # 记录这次失败的选择，用于学习
                reward = -5  # 负奖励，因为选择了不可能完成的任务
                next_state = state  # 状态不变
                self.update_q_table(state, vehicle, reward, next_state)
                continue
            
            # 检查电池是否足够完成任务
            trip_to_vehicle = robot.battery_needed_for_trip(vehicle.position, False)
            charge_need = vehicle.required_charge - vehicle.current_charge
            estimated_charging = charge_need * 0.5  # 估计充电消耗
            trip_back = robot.battery_needed_for_trip(robot.find_nearest_charging_station(), False)
            total_energy_needed = trip_to_vehicle + estimated_charging + trip_back
            
            if robot.battery and robot.battery.current_charge > total_energy_needed * 1.3:  # 30%的安全边际
                # 分配任务
                robot.status = "moving_to_vehicle"
                robot.target_vehicle = vehicle
                vehicle.assigned_robot = robot
                vehicle.status = "assigned"
                
                # 计算奖励
                reward = self.calculate_reward(robot, vehicle, self.sim.current_time)
                
                # 获取新状态
                next_state = self.get_state(robot, [v for v in waiting_vehicles if v != vehicle])
                
                # 更新Q表
                self.update_q_table(state, vehicle, reward, next_state)
                
                # 从等待列表中移除
                waiting_vehicles.remove(vehicle)
                
                self.sim.log(f"{self.sim.current_time}分钟: [RL] 机器人{robot.id}分配到车辆{vehicle.id}，预期奖励{reward:.2f}")
            else:
                # 电量不足，记录这次失败的选择
                reward = -8  # 更大的负奖励，因为这种错误是可以避免的
                next_state = state  # 状态不变
                self.update_q_table(state, vehicle, reward, next_state)


class RLChargingSimulation(ChargingSimulation):
    """使用强化学习的充电模拟类 - 改进版"""
    
    def __init__(self, scale="小规模"):
        super().__init__(scale=scale, scheduling_strategy="rl")
        self.rl_scheduler = RLRobotScheduler(self)
        
        # 强化学习专用的参数
        self.episode_rewards = []
        self.current_episode_reward = 0
        self.training_episodes = 0  # 追踪学习进度
    
    def assign_tasks(self):
        """使用RL方法分配任务"""
        # 更新所有等待车辆的优先级
        self.update_vehicle_priorities()
        
        # 获取所有等待充电的车辆
        waiting_vehicles = self.waiting_vehicles
        
        if not waiting_vehicles:
            return
        
        # 获取所有空闲的机器人
        idle_robots = [r for r in self.robots 
                      if r.status == "idle" 
                      and r.battery 
                      and r.battery.current_charge > 15]  # 确保有足够电量执行任务
        
        if not idle_robots:
            return
        
        # 使用RL调度器分配任务
        self.rl_scheduler.assign_rl_tasks(waiting_vehicles, idle_robots)
        
        # 记录本次分配的奖励总和
        self.current_episode_reward += sum(robot.target_vehicle is not None for robot in idle_robots) * 0.5
    
    def handle_task_completion(self, robot):
        """重写任务完成处理，添加RL奖励机制"""
        vehicle = robot.target_vehicle
        
        if not vehicle or vehicle.status == "failed":
            # 车辆已经离开或处理完毕
            robot.status = "returning"
            robot.target_vehicle = None
            return
        
        if vehicle.current_charge >= vehicle.required_charge:
            # 充电完成 - 给予额外奖励
            vehicle.status = "completed"
            vehicle.charging_end_time = self.current_time
            self.completed_vehicles.append(vehicle)
            self.stats["completed_count"] += 1
            
            # 计算等待和充电时间
            if vehicle.charging_start_time is not None:
                waiting_time = vehicle.charging_start_time - vehicle.arrival_time
                charging_time = self.current_time - vehicle.charging_start_time
                self.stats["total_waiting_time"] += waiting_time
                self.stats["total_charging_time"] += charging_time
            
            # 计算RL奖励
            reward = 10  # 基础奖励
            
            # 时间效率奖励
            if vehicle.charging_start_time is not None:
                time_efficiency = min(10, 300 / max(10, charging_time))  # 充电效率奖励
                reward += time_efficiency
            
            # 为紧急车辆提供服务的额外奖励
            time_left_at_start = vehicle.departure_time - vehicle.charging_start_time if vehicle.charging_start_time else 0
            if time_left_at_start < 60:
                reward += 5  # 成功完成紧急任务
            
            # 累加奖励
            self.current_episode_reward += reward
            
            self.log(f"{self.current_time}分钟: 机器人{robot.id}完成对车辆{vehicle.id}的充电任务，当前电量{vehicle.current_charge:.1f}kWh，RL奖励+{reward:.1f}")
        
        robot.status = "returning"
        robot.target_vehicle = None
        vehicle.assigned_robot = None
    
    def run(self):
        """重写运行方法，包含强化学习的周期管理"""
        # 重置本周期奖励
        self.current_episode_reward = 0
        self.training_episodes += 1
        
        # 运行模拟
        stats = super().run()
        
        # 记录本周期的总奖励
        self.episode_rewards.append(self.current_episode_reward)
        
        # 调整探索率 - 随着学习进行逐渐降低探索
        if self.training_episodes % 5 == 0 and self.rl_scheduler.epsilon > 0.05:
            self.rl_scheduler.epsilon *= 0.95
            self.log(f"强化学习探索率调整为: {self.rl_scheduler.epsilon:.3f}")
        
        # 打印学习进度
        avg_reward = sum(self.episode_rewards[-5:]) / min(5, len(self.episode_rewards)) if self.episode_rewards else 0
        self.log(f"强化学习周期 {self.training_episodes} 完成，总奖励: {self.current_episode_reward:.1f}，最近5次平均: {avg_reward:.1f}")
        
        return stats


def visualize_results(results, problem_scales):
    """可视化不同策略和问题规模的结果 - 增强版"""
    strategies = list(results.keys())
    scales = list(problem_scales.keys())
    
    # 设置统一的样式
    plt.style.use('seaborn-v0_8-darkgrid')
    colors = plt.cm.viridis(np.linspace(0, 1, len(strategies)))
    
    # 创建子图网格
    fig = plt.figure(figsize=(18, 14))
    gs = fig.add_gridspec(3, 2, hspace=0.3, wspace=0.3)
    
    # 1. 完成率对比
    ax1 = fig.add_subplot(gs[0, 0])
    completion_rates = {}
    for i, strategy in enumerate(strategies):
        completion_rates[strategy] = [results[strategy][scale]["completion_rate"] for scale in scales]
        ax1.plot(scales, completion_rates[strategy], 'o-', lw=2, color=colors[i], label=strategy)
    
    ax1.set_xlabel('问题规模', fontsize=12)
    ax1.set_ylabel('完成率 (%)', fontsize=12)
    ax1.set_title('不同策略和规模下的任务完成率', fontsize=14, fontweight='bold')
    ax1.grid(True, linestyle='--', alpha=0.7)
    
    # 添加数据标签
    for i, strategy in enumerate(strategies):
        for j, value in enumerate(completion_rates[strategy]):
            ax1.annotate(f'{value:.1f}%', 
                       xy=(scales[j], value), 
                       xytext=(0, 10),
                       textcoords='offset points',
                       ha='center', va='bottom',
                       fontsize=9, fontweight='bold')
    
    ax1.legend(loc='upper center', bbox_to_anchor=(0.5, -0.15), ncol=len(strategies))
    
    # 2. 平均等待时间对比
    ax2 = fig.add_subplot(gs[0, 1])
    waiting_times = {}
    for i, strategy in enumerate(strategies):
        waiting_times[strategy] = [results[strategy][scale]["avg_waiting_time"] for scale in scales]
        ax2.plot(scales, waiting_times[strategy], 'o-', lw=2, color=colors[i], label=strategy)
    
    ax2.set_xlabel('问题规模', fontsize=12)
    ax2.set_ylabel('平均等待时间 (分钟)', fontsize=12)
    ax2.set_title('不同策略和规模下的平均等待时间', fontsize=14, fontweight='bold')
    ax2.grid(True, linestyle='--', alpha=0.7)
    
    # 添加数据标签
    for i, strategy in enumerate(strategies):
        for j, value in enumerate(waiting_times[strategy]):
            ax2.annotate(f'{value:.1f}', 
                       xy=(scales[j], value), 
                       xytext=(0, 10),
                       textcoords='offset points',
                       ha='center', va='bottom',
                       fontsize=9)
    
    # 3. 机器人利用率对比
    ax3 = fig.add_subplot(gs[1, 0])
    utilization_rates = {}
    for i, strategy in enumerate(strategies):
        utilization_rates[strategy] = [results[strategy][scale]["avg_robot_utilization"] for scale in scales]
        ax3.plot(scales, utilization_rates[strategy], 'o-', lw=2, color=colors[i], label=strategy)
    
    ax3.set_xlabel('问题规模', fontsize=12)
    ax3.set_ylabel('机器人平均利用率 (%)', fontsize=12)
    ax3.set_title('不同策略和规模下的机器人利用率', fontsize=14, fontweight='bold')
    ax3.grid(True, linestyle='--', alpha=0.7)
    
    # 添加数据标签
    for i, strategy in enumerate(strategies):
        for j, value in enumerate(utilization_rates[strategy]):
            ax3.annotate(f'{value:.1f}%', 
                       xy=(scales[j], value), 
                       xytext=(0, 10),
                       textcoords='offset points',
                       ha='center', va='bottom',
                       fontsize=9)
    
    # 4. 电池交换次数对比
    ax4 = fig.add_subplot(gs[1, 1])
    battery_swaps = {}
    for i, strategy in enumerate(strategies):
        battery_swaps[strategy] = [results[strategy][scale]["battery_swaps"] for scale in scales]
        ax4.plot(scales, battery_swaps[strategy], 'o-', lw=2, color=colors[i], label=strategy)
    
    ax4.set_xlabel('问题规模', fontsize=12)
    ax4.set_ylabel('电池交换次数', fontsize=12)
    ax4.set_title('不同策略和规模下的电池交换次数', fontsize=14, fontweight='bold')
    ax4.grid(True, linestyle='--', alpha=0.7)
    
    # 添加数据标签
    for i, strategy in enumerate(strategies):
        for j, value in enumerate(battery_swaps[strategy]):
            ax4.annotate(f'{value}', 
                       xy=(scales[j], value), 
                       xytext=(0, 10),
                       textcoords='offset points',
                       ha='center', va='bottom',
                       fontsize=9)
    
    # 5. 综合性能雷达图
    ax5 = fig.add_subplot(gs[2, :], polar=True)
    
    # 定义评估指标
    metrics = ['完成率', '等待时间\n(反向)', '机器人\n利用率', '电池交换\n效率', '任务\n分配速度']
    metrics_count = len(metrics)
    
    # 角度设置
    angles = np.linspace(0, 2*np.pi, metrics_count, endpoint=False).tolist()
    angles += angles[:1]  # 闭合
    
    # 为每个策略绘制雷达图
    for i, strategy in enumerate(strategies):
        # 收集大规模问题下的各项指标值
        values = []
        
        # 完成率 (0-100)
        completion = results[strategy]["大规模"]["completion_rate"]
        values.append(completion)
        
        # 等待时间 (反向，越小越好，范围调整到0-100)
        wait_time = results[strategy]["大规模"]["avg_waiting_time"]
        max_wait_time = max([results[s]["大规模"]["avg_waiting_time"] for s in strategies])
        wait_score = 100 * (1 - wait_time / max_wait_time) if max_wait_time > 0 else 50
        values.append(wait_score)
        
        # 机器人利用率 (0-100)
        utilization = results[strategy]["大规模"]["avg_robot_utilization"]
        values.append(min(100, utilization))  # 防止超过100
        
        # 电池交换效率 (按照完成任务数/电池交换次数评估，归一化到0-100)
        completed = results[strategy]["大规模"]["completed_count"]
        swaps = results[strategy]["大规模"]["battery_swaps"]
        swap_efficiency = 100 * (completed / max(1, swaps)) / 2  # 除以2使得范围在0-100左右
        values.append(min(100, swap_efficiency))
        
        # 任务分配速度 (基于算法复杂度的主观评分，1-5，再乘以20)
        if strategy == "nearest_first":
            speed_score = 90  # 简单高效
        elif strategy == "most_urgent_first":
            speed_score = 70  # 中等复杂度
        elif strategy == "hybrid_strategy":
            speed_score = 60  # 较复杂
        elif strategy == "rl":
            speed_score = 50  # 复杂，需要学习
        else:
            speed_score = 75  # 默认值
        values.append(speed_score)
        
        # 闭合雷达图
        values += values[:1]
        
        # 绘制
        ax5.plot(angles, values, 'o-', lw=2, color=colors[i], label=strategy)
        ax5.fill(angles, values, color=colors[i], alpha=0.25)
    
    # 设置雷达图属性
    ax5.set_xticks(angles[:-1])
    ax5.set_xticklabels(metrics, fontsize=11)
    ax5.set_yticks([20, 40, 60, 80, 100])
    ax5.set_yticklabels(['20', '40', '60', '80', '100'], fontsize=9)
    ax5.set_ylim(0, 100)
    ax5.set_title('大规模问题下不同策略的综合性能评估', fontsize=14, fontweight='bold', pad=20)
    ax5.legend(loc='upper center', bbox_to_anchor=(0.5, -0.05), ncol=len(strategies))
    
    # 保存图表
    plt.tight_layout()
    plt.savefig('charging_strategies_comparison.png', dpi=300, bbox_inches='tight')
    plt.close(fig)
    
    # 额外创建一个表格形式的结果展示
    fig, ax = plt.figure(figsize=(12, 8)), plt.subplot(111)
    ax.axis('off')
    ax.axis('tight')
    
    # 准备表格数据
    table_data = []
    headers = ['策略', '规模', '完成率 (%)', '平均等待时间 (分钟)', '平均充电时间 (分钟)', '机器人利用率 (%)', '电池交换次数']
    
    for strategy in strategies:
        for scale in scales:
            data = results[strategy][scale]
            row = [
                strategy,
                scale,
                f"{data['completion_rate']:.1f}",
                f"{data['avg_waiting_time']:.1f}",
                f"{data['avg_charging_time']:.1f}",
                f"{data['avg_robot_utilization']:.1f}",
                f"{data['battery_swaps']}"
            ]
            table_data.append(row)
    
    # 创建表格
    table = ax.table(cellText=table_data, colLabels=headers, loc='center', cellLoc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.2, 1.5)
    
    # 设置表格样式
    for (i, j), cell in table.get_celld().items():
        if i == 0:  # 表头行
            cell.set_text_props(fontweight='bold', color='white')
            cell.set_facecolor('#4472C4')
        elif i % 3 == 1:  # 每个策略的第一个规模
            cell.set_facecolor('#E6F0FF')
        elif i % 3 == 2:  # 每个策略的第二个规模 
            cell.set_facecolor('#D6E5FF')
        else:  # 每个策略的第三个规模
            cell.set_facecolor('#C6DBFF')
            
        if j == 0 and i > 0:  # 策略名称列
            prev_strategy = table_data[i-1][0] if i > 1 else None
            curr_strategy = table_data[i-1][0]
            if i == 1 or prev_strategy != curr_strategy:
                cell.set_text_props(fontweight='bold')
    
    plt.title('充电机器人调度策略性能对比表', fontsize=16, fontweight='bold', pad=20)
    plt.tight_layout()
    plt.savefig('charging_strategies_table.png', dpi=300, bbox_inches='tight')
    plt.close()


def run_simulation(strategies, problem_scales):
    """运行不同策略和规模的模拟 - 增强版"""
    results = {}
    
    for strategy in strategies:
        results[strategy] = {}
        for scale in problem_scales:
            print(f"运行 {strategy} 策略，{scale}规模...")
            
            # 创建合适的模拟实例
            if strategy == "rl":
                sim = RLChargingSimulation(scale=scale)
            else:
                sim = ChargingSimulation(scale=scale, scheduling_strategy=strategy)
            
            # 设置和运行
            sim.setup()
            stats = sim.run()
            results[strategy][scale] = stats
            
            # 输出关键指标
            print(f"  完成率: {stats['completion_rate']:.2f}%")
            print(f"  完成车辆数: {stats['completed_count']}")
            print(f"  失败车辆数: {stats['failed_count']}")
            print(f"  平均等待时间: {stats['avg_waiting_time']:.2f}分钟")
            print(f"  平均充电时间: {stats['avg_charging_time']:.2f}分钟")
            print(f"  机器人平均利用率: {stats['avg_robot_utilization']:.2f}%")
            print(f"  电池更换次数: {stats['battery_swaps']}")
            
            # 保存更详细的日志（可选）
            with open(f"{strategy}_{scale}_log.txt", "w") as f:
                for log in sim.logs[-100:]:  # 只保存最后100条日志避免文件过大
                    f.write(log + "\n")
    
    return results


# 主函数：运行模拟并比较不同策略
def main():
    # 定义不同的调度策略，包含新的混合策略
    strategies = [
        "nearest_first",       # 最近任务优先
        "max_charge_need_first", # 最大充电需求优先
        "earliest_deadline_first", # 最早截止时间优先
        "most_urgent_first",   # 最紧急任务优先
        "hybrid_strategy",     # 新增：混合策略
    ]
    
    # 运行模拟
    results = run_simulation(strategies, PROBLEM_SCALES)
    
    # 可视化结果
    visualize_results(results, PROBLEM_SCALES)
    
    # 额外：运行强化学习调度模型
    print("\n运行强化学习调度模型...")
    rl_results = {}
    for scale in PROBLEM_SCALES:
        print(f"运行 RL 策略，{scale}规模...")
        sim = RLChargingSimulation(scale=scale)
        sim.setup()
        stats = sim.run()
        if "rl" not in rl_results:
            rl_results["rl"] = {}
        rl_results["rl"][scale] = stats
        
        print(f"  完成率: {stats['completion_rate']:.2f}%")
        print(f"  平均等待时间: {stats['avg_waiting_time']:.2f}分钟")
        print(f"  平均充电时间: {stats['avg_charging_time']:.2f}分钟")
        print(f"  机器人平均利用率: {stats['avg_robot_utilization']:.2f}%")
    
    # 合并结果并重新可视化
    combined_results = {**results, **rl_results}
    visualize_results(combined_results, PROBLEM_SCALES)
    
    # 比较最佳策略
    print("\n策略性能对比：")
    for scale in PROBLEM_SCALES:
        best_strategy = max(combined_results.keys(), 
                          key=lambda s: combined_results[s][scale]["completion_rate"])
        print(f"{scale}问题最佳策略: {best_strategy}, "
             f"完成率: {combined_results[best_strategy][scale]['completion_rate']:.2f}%")


if __name__ == "__main__":
    main()