import pygame
import sys
import random
import math
from charging_robots_simulation import ChargingSimulation, CHARGING_STATION_POS, PARK_WIDTH, PARK_HEIGHT

# 初始化pygame
pygame.init()

# 颜色定义
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)
GRAY = (200, 200, 200)

# 游戏设置
SCREEN_WIDTH = 1200
SCREEN_HEIGHT = 800
SCALE_FACTOR = min(SCREEN_WIDTH / PARK_WIDTH, SCREEN_HEIGHT / PARK_HEIGHT) * 0.8
OFFSET_X = (SCREEN_WIDTH - PARK_WIDTH * SCALE_FACTOR) / 2
OFFSET_Y = (SCREEN_HEIGHT - PARK_HEIGHT * SCALE_FACTOR) / 2
FPS = 60

# 创建屏幕
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Charging Robots Simulation")
clock = pygame.time.Clock()

# 字体
font = pygame.font.SysFont(None, 24)
large_font = pygame.font.SysFont(None, 32)

def world_to_screen(pos):
    """将世界坐标转换为屏幕坐标"""
    x, y = pos
    screen_x = x * SCALE_FACTOR + OFFSET_X
    screen_y = y * SCALE_FACTOR + OFFSET_Y
    return (screen_x, screen_y)

def draw_vehicle(vehicle):
    """绘制车辆"""
    pos = world_to_screen(vehicle.position)
    
    # 根据状态选择颜色
    if vehicle.status == "waiting":
        color = RED
    elif vehicle.status == "charging":
        color = BLUE
    elif vehicle.status == "completed":
        color = GREEN
    else:  # assigned or failed
        color = YELLOW
        
    # 绘制车辆形状
    pygame.draw.circle(screen, color, (int(pos[0]), int(pos[1])), 10)
    
    # 显示车辆ID
    id_text = font.render(str(vehicle.id), True, BLACK)
    screen.blit(id_text, (int(pos[0]) - 5, int(pos[1]) - 8))
    
    # 显示电量
    charge_text = font.render(f"{vehicle.current_charge:.0f}/{vehicle.required_charge:.0f}", True, BLACK)
    screen.blit(charge_text, (int(pos[0]) - 20, int(pos[1]) + 10))

def draw_robot(robot):
    """改进机器人绘制逻辑"""
    if robot is None or not hasattr(robot, 'position'):
        return
        
    pos = world_to_screen(robot.position)
    
    # 根据状态选择颜色
    if robot.status == "idle":
        color = GRAY
    elif robot.status == "moving_to_vehicle":
        color = BLUE
    elif robot.status == "returning":
        color = YELLOW
    elif robot.status == "charging_vehicle":
        color = GREEN
    else:  # 其他状态
        color = ORANGE
    
    # 绘制机器人外框
    robot_rect = pygame.Rect(0, 0, 18, 18)
    robot_rect.center = pos
    pygame.draw.rect(screen, BLACK, robot_rect)
    
    # 绘制机器人内部
    inner_rect = pygame.Rect(0, 0, 16, 16)
    inner_rect.center = pos
    pygame.draw.rect(screen, color, inner_rect)
    
    # 显示机器人ID
    id_text = font.render(str(robot.id), True, WHITE)
    id_rect = id_text.get_rect(center=pos)
    screen.blit(id_text, id_rect)
    
    # 显示电池电量（如果有电池）- 在机器人下方
    if hasattr(robot, 'battery') and robot.battery and robot.battery is not None:
        try:
            # 检查battery.current_charge属性是否存在且不为None
            if hasattr(robot.battery, 'current_charge') and robot.battery.current_charge is not None:
                battery_text = font.render(f"{int(robot.battery.current_charge)}", True, BLACK)
                battery_rect = battery_text.get_rect(midtop=(pos[0], pos[1] + 15))
                screen.blit(battery_text, battery_rect)
                
                # 添加电池电量百分比可视化
                max_capacity = robot.battery.max_capacity if hasattr(robot.battery, 'max_capacity') else 50.0
                percent = min(100, int(robot.battery.current_charge / max_capacity * 100))
                bar_width = 30
                pygame.draw.rect(screen, BLACK, (pos[0] - bar_width/2 - 1, pos[1] + 35 - 1, bar_width + 2, 7))
                if percent > 20:
                    bar_color = GREEN
                elif percent > 10:
                    bar_color = YELLOW
                else:
                    bar_color = RED
                pygame.draw.rect(screen, bar_color, (pos[0] - bar_width/2, pos[1] + 35, bar_width * percent / 100, 5))
        except (AttributeError, TypeError, ZeroDivisionError) as e:
            # 调试输出，帮助识别问题
            if debug_mode:
                print(f"电池绘制错误: {e} - 机器人ID: {robot.id}")
    
    # 如果机器人有目标车辆，绘制连接线
    if hasattr(robot, 'target_vehicle') and robot.target_vehicle:
        try:
            target_pos = world_to_screen(robot.target_vehicle.position)
            pygame.draw.line(screen, BLUE, pos, target_pos, 2)
        except (AttributeError, TypeError) as e:
            # 处理可能的属性错误
            pass

def draw_charging_station():
    """绘制充电站"""
    pos = world_to_screen(CHARGING_STATION_POS)
    pygame.draw.rect(screen, GREEN, (int(pos[0]) - 20, int(pos[1]) - 20, 40, 40))
    station_text = font.render("CS", True, BLACK)
    screen.blit(station_text, (int(pos[0]) - 10, int(pos[1]) - 8))

def draw_status_panel(sim):
    """绘制状态面板"""
    # 背景
    pygame.draw.rect(screen, WHITE, (0, 0, 300, 150))
    pygame.draw.rect(screen, BLACK, (0, 0, 300, 150), 1)
    
    # 模拟时间
    time_text = large_font.render(f"Time: {sim.current_time//60}:{sim.current_time%60:02d}", True, BLACK)
    screen.blit(time_text, (10, 10))
    
    # 统计信息
    completed_text = font.render(f"Completed: {sim.stats['completed_count']}", True, GREEN)
    screen.blit(completed_text, (10, 50))
    
    failed_text = font.render(f"Failed: {sim.stats['failed_count']}", True, RED)
    screen.blit(failed_text, (10, 80))
    
    total = sim.stats['completed_count'] + sim.stats['failed_count']
    rate = 0 if total == 0 else (sim.stats['completed_count'] / total * 100)
    rate_text = font.render(f"Completion Rate: {rate:.1f}%", True, BLUE)
    screen.blit(rate_text, (10, 110))

def run_game(scale="中规模", strategy="nearest_first", speed=1):
    """运行游戏主循环"""
    # 创建模拟
    sim = ChargingSimulation(scale=scale, scheduling_strategy=strategy)
    sim.setup()
    
    running = True
    paused = False
    
    while running:
        # 处理事件
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    paused = not paused
                elif event.key == pygame.K_UP:
                    speed = min(10, speed + 1)
                elif event.key == pygame.K_DOWN:
                    speed = max(1, speed - 1)
                elif event.key == pygame.K_ESCAPE:
                    running = False
        
        # 清屏
        screen.fill(WHITE)
        
        # 绘制园区边界
        park_rect = pygame.Rect(
            OFFSET_X, OFFSET_Y, 
            PARK_WIDTH * SCALE_FACTOR, PARK_HEIGHT * SCALE_FACTOR
        )
        pygame.draw.rect(screen, BLACK, park_rect, 1)
        
        # 绘制充电站
        draw_charging_station()
        
        # 如果没有暂停，更新模拟状态
        if not paused:
            for _ in range(speed):
                # 执行模拟的一个时间步
                sim.update_status()
                sim.assign_tasks()
                
                # 增加当前时间
                sim.current_time += 1
                
                # 处理模拟结束
                if sim.current_time >= 24 * 60:  # 24小时
                    sim.calculate_final_stats()
                    print("模拟完成")
                    print(f"完成率: {sim.stats['completion_rate']:.2f}%")
                    print(f"平均等待时间: {sim.stats['avg_waiting_time']:.2f}分钟")
                    print(f"平均充电时间: {sim.stats['avg_charging_time']:.2f}分钟")
                    running = False
                    break
        
        # 绘制所有实体
        for vehicle in sim.vehicles:
            draw_vehicle(vehicle)
        
        for robot in sim.robots:
            draw_robot(robot)
        
        # 绘制状态面板
        draw_status_panel(sim)
        
        # 显示模拟速度
        speed_text = font.render(f"Speed: {speed}x", True, BLACK)
        screen.blit(speed_text, (SCREEN_WIDTH - 100, 10))
        
        # 如果暂停，显示暂停文本
        if paused:
            pause_text = large_font.render("PAUSED", True, RED)
            screen.blit(pause_text, (SCREEN_WIDTH//2 - 50, 10))
        
        # 更新屏幕
        pygame.display.flip()
        clock.tick(FPS)
    
    pygame.quit()
    return sim.stats

if __name__ == "__main__":
    # 选择要运行的规模和策略
    scale = "中规模"
    strategy = "nearest_first"
    
    # 运行游戏
    stats = run_game(scale, strategy)
    
    # 打印最终统计
    print("\n最终统计：")
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"{key}: {value:.2f}")
        else:
            print(f"{key}: {value}")