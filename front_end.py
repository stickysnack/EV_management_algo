# import matplotlib.pyplot as plt
# import matplotlib.animation as animation
# import matplotlib.patches as patches
# import numpy as np
# from matplotlib.colors import LinearSegmentedColormap
# import random
# from IPython.display import HTML

# class ParkVisualization:
#     """园区可视化工具"""
    
#     def __init__(self, simulation):
#         self.sim = simulation
#         self.fig, self.ax = plt.subplots(figsize=(10, 8))
#         self.robot_plots = {}
#         self.vehicle_plots = {}
#         self.texts = []
        
#         # 设置园区边界
#         self.ax.set_xlim(0, PARK_WIDTH)
#         self.ax.set_ylim(0, PARK_HEIGHT)
#         self.ax.set_title('园区充电机器人调度模拟')
#         self.ax.set_xlabel('X 坐标 (米)')
#         self.ax.set_ylabel('Y 坐标 (米)')
        
#         # 绘制充电站
#         station = patches.Rectangle(
#             (CHARGING_STATION_POS[0]-30, CHARGING_STATION_POS[1]-30),
#             60, 60, linewidth=1, edgecolor='r', facecolor='lightgray', alpha=0.7)
#         self.ax.add_patch(station)
#         self.ax.text(CHARGING_STATION_POS[0], CHARGING_STATION_POS[1], 
#                     '充电站', ha='center', va='center')
        
#         # 添加状态信息文本
#         self.status_text = self.ax.text(0.02, 0.98, '', transform=self.ax.transAxes,
#                                       verticalalignment='top', fontsize=9)
    
#     def init_frame(self):
#         """初始化动画帧"""
#         # 创建机器人和车辆的散点图
#         for robot in self.sim.robots:
#             robot_plot, = self.ax.plot([], [], 'bs', markersize=8)
#             self.robot_plots[robot.id] = robot_plot
        
#         for vehicle in self.sim.vehicles:
#             if vehicle.arrival_time <= 0:
#                 vehicle_plot, = self.ax.plot([], [], 'go', markersize=6)
#                 self.vehicle_plots[vehicle.id] = vehicle_plot
        
#         return list(self.robot_plots.values()) + list(self.vehicle_plots.values()) + [self.status_text]
    
#     def update_frame(self, frame):
#         """更新动画帧"""
#         current_time = frame  # 当前模拟时间
        
#         # 更新机器人位置
#         for robot in self.sim.robots:
#             if robot.id in self.robot_plots:
#                 self.robot_plots[robot.id].set_data([robot.position[0]], [robot.position[1]])
                
#                 # 根据状态更改颜色
#                 if robot.status == "idle":
#                     self.robot_plots[robot.id].set_color('blue')
#                 elif robot.status == "moving_to_vehicle":
#                     self.robot_plots[robot.id].set_color('cyan')
#                 elif robot.status == "charging_vehicle":
#                     self.robot_plots[robot.id].set_color('magenta')
#                 elif robot.status == "returning":
#                     self.robot_plots[robot.id].set_color('purple')
        
#         # 更新车辆位置和状态
#         for vehicle in self.sim.vehicles:
#             if vehicle.arrival_time <= current_time and vehicle.departure_time > current_time:
#                 if vehicle.id not in self.vehicle_plots:
#                     vehicle_plot, = self.ax.plot([], [], 'go', markersize=6)
#                     self.vehicle_plots[vehicle.id] = vehicle_plot
                
#                 self.vehicle_plots[vehicle.id].set_data([vehicle.position[0]], [vehicle.position[1]])
                
#                 # 根据状态更改颜色
#                 if vehicle.status == "waiting":
#                     self.vehicle_plots[vehicle.id].set_color('green')
#                 elif vehicle.status == "assigned":
#                     self.vehicle_plots[vehicle.id].set_color('yellow')
#                 elif vehicle.status == "charging":
#                     self.vehicle_plots[vehicle.id].set_color('orange')
#                 elif vehicle.status == "completed":
#                     self.vehicle_plots[vehicle.id].set_color('darkgreen')
#             elif vehicle.id in self.vehicle_plots:
#                 if vehicle.departure_time <= current_time:
#                     # 车辆已离开
#                     self.vehicle_plots[vehicle.id].set_data([], [])
        
#         # 更新状态信息
#         active_vehicles = len([v for v in self.sim.vehicles if v.arrival_time <= current_time and v.departure_time > current_time])
#         completed = len([v for v in self.sim.completed_vehicles if v.departure_time <= current_time])
#         failed = len([v for v in self.sim.failed_vehicles if v.departure_time <= current_time])
        
#         status_str = f'时间: {current_time} 分钟\n'
#         status_str += f'活跃车辆: {active_vehicles}\n'
#         status_str += f'已完成充电: {completed}\n'
#         status_str += f'未完成充电: {failed}\n'
        
#         self.status_text.set_text(status_str)
        
#         # 返回所有更新的对象
#         return list(self.robot_plots.values()) + list(self.vehicle_plots.values()) + [self.status_text]
    
#     def create_animation(self, duration=500, interval=200):
#         """创建动画"""
#         ani = animation.FuncAnimation(self.fig, self.update_frame, frames=range(duration),
#                                      init_func=self.init_frame, blit=True, interval=interval)
#         plt.close(self.fig)  # 避免显示静态图
#         return ani


# def run_visual_demo():
#     """运行可视化演示"""
#     # 创建小规模测试
#     sim = ChargingSimulation(scale="小规模", scheduling_strategy="most_urgent_first")
#     sim.setup()
    
#     # 创建可视化
#     vis = ParkVisualization(sim)
    
#     # 显式运行一些时间步以更新模拟状态
#     for _ in range(100):
#         sim.current_time += 1
#         sim.update_status()
#         if sim.current_time % 5 == 0:
#             sim.assign_tasks()
    
#     # 创建并返回动画
#     ani = vis.create_animation(duration=200)
#     return HTML(ani.to_jshtml())

# # 运行可视化演示
# # run_visual_demo()