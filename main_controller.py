import sys
import os

import pygame
from charging_robots_simulation import ChargingSimulation, PROBLEM_SCALES

# 导入游戏模块（假设充电机器人游戏文件名为charging_robots_game.py）
try:
    from charging_robots_game import run_game
except ImportError:
    print("游戏模块未找到，请确保charging_robots_game.py文件存在")
    run_game = None

# 导入比较策略模块
try:
    from compare_strategies import run_comparative_simulation, run_all_comparisons
except ImportError:
    print("比较策略模块未找到，请确保compare_strategies.py文件存在")
    run_comparative_simulation = None
    run_all_comparisons = None

def print_header():
    """打印程序标题"""
    print("="*60)
    print("充电机器人调度模拟系统".center(54))
    print("="*60)

def create_results_dir():
    """创建结果目录"""
    if not os.path.exists("results"):
        os.makedirs("results")
        print("创建结果目录: results/")

def main_menu():
    """显示主菜单并处理用户选择"""
    while True:
        print_header()
        print("\n主菜单:")
        print("1. 运行可视化模拟")
        print("2. 比较调度策略")
        print("3. 运行所有规模的比较")
        print("4. 退出")
        
        choice = input("\n请选择 (1-4): ")
        
        if choice == "1":
            if run_game:
                run_visualization_menu()
            else:
                print("\n错误: 游戏模块未找到。请确保charging_robots_game.py文件存在。")
                input("按Enter键继续...")
        elif choice == "2":
            if run_comparative_simulation:
                run_comparison_menu()
            else:
                print("\n错误: 比较策略模块未找到。请确保compare_strategies.py文件存在。")
                input("按Enter键继续...")
        elif choice == "3":
            if run_all_comparisons:
                create_results_dir()
                print("\n运行所有规模的比较...")
                run_all_comparisons()
                print("\n所有比较完成！结果已保存到results目录。")
                input("按Enter键继续...")
            else:
                print("\n错误: 比较策略模块未找到。请确保compare_strategies.py文件存在。")
                input("按Enter键继续...")
        elif choice == "4":
            print("\n感谢使用充电机器人调度模拟系统！")
            sys.exit(0)
        else:
            print("\n无效选择，请重试。")
            input("按Enter键继续...")

def run_visualization_menu():
    """可视化模拟菜单"""
    while True:
        print_header()
        print("\n可视化模拟设置:")
        
        # 选择规模
        print("\n选择问题规模:")
        print("1. 小规模")
        print("2. 中规模")
        print("3. 大规模")
        print("4. 返回主菜单")
        
        scale_choice = input("\n请选择规模 (1-4): ")
        
        if scale_choice == "4":
            return
        
        if scale_choice == "1":
            scale = "小规模"
        elif scale_choice == "2":
            scale = "中规模"
        elif scale_choice == "3":
            scale = "大规模"
        else:
            print("\n无效选择，请重试。")
            input("按Enter键继续...")
            continue
        
        # 选择策略
        print("\n选择调度策略:")
        print("1. 最近优先")
        print("2. 最大充电需求优先")
        print("3. 最早截止时间优先")
        print("4. 最紧急任务优先")
        print("5. 返回规模选择")
        
        strategy_choice = input("\n请选择策略 (1-5): ")
        
        if strategy_choice == "5":
            continue
        
        if strategy_choice == "1":
            strategy = "nearest_first"
        elif strategy_choice == "2":
            strategy = "max_charge_need_first"
        elif strategy_choice == "3":
            strategy = "earliest_deadline_first"
        elif strategy_choice == "4":
            strategy = "most_urgent_first"
        else:
            print("\n无效选择，请重试。")
            input("按Enter键继续...")
            continue
        
        # 运行可视化模拟
        print(f"\n运行{scale}的{strategy}策略可视化模拟...")
        print("\n按空格键暂停/继续模拟")
        print("按上/下箭头键调整模拟速度")
        print("按ESC键退出模拟")
        input("按Enter键开始...")
        
        # 运行游戏
        stats = run_game(scale, strategy)
        
        # 显示结果
        print("\n模拟结束！结果:")
        print(f"完成率: {stats['completion_rate']:.2f}%")
        print(f"完成车辆数: {stats['completed_count']}")
        print(f"失败车辆数: {stats['failed_count']}")
        print(f"平均等待时间: {stats['avg_waiting_time']:.2f}分钟")
        print(f"平均充电时间: {stats['avg_charging_time']:.2f}分钟")
        print(f"机器人平均利用率: {stats['avg_robot_utilization']:.2f}%")
        print(f"电池更换次数: {stats['battery_swaps']}")
        
        input("\n按Enter键返回菜单...")
        return

def run_comparison_menu():
    """比较策略菜单"""
    print_header()
    print("\n比较调度策略设置:")
    
    # 选择规模
    print("\n选择问题规模:")
    print("1. 小规模")
    print("2. 中规模")
    print("3. 大规模")
    print("4. 返回主菜单")
    
    scale_choice = input("\n请选择规模 (1-4): ")
    
    if scale_choice == "4":
        return
    
    if scale_choice == "1":
        scale = "小规模"
    elif scale_choice == "2":
        scale = "中规模"
    elif scale_choice == "3":
        scale = "大规模"
    else:
        print("\n无效选择，请重试。")
        input("按Enter键继续...")
        return
    
    # 创建结果目录
    create_results_dir()
    
    # 运行比较
    print(f"\n运行{scale}规模的策略比较...")
    results = run_comparative_simulation(scale=scale)
    
    # 显示结果
    print("\n比较完成！结果:")
    
    # 计算最佳策略
    best_completion = max(results.items(), key=lambda x: x[1]["completion_rate"])[0]
    best_waiting = min(results.items(), key=lambda x: x[1]["avg_waiting_time"])[0]
    best_utilization = max(results.items(), key=lambda x: x[1]["avg_robot_utilization"])[0]
    
    print(f"最高完成率: {best_completion} ({results[best_completion]['completion_rate']:.1f}%)")
    print(f"最低等待时间: {best_waiting} ({results[best_waiting]['avg_waiting_time']:.1f}分钟)")
    print(f"最高机器人利用率: {best_utilization} ({results[best_utilization]['avg_robot_utilization']:.1f}%)")
    
    print("\n详细结果已保存到 results 目录。")
    input("\n按Enter键返回主菜单...")

if __name__ == "__main__":
    # 初始化
    create_results_dir()
    
    # 显示主菜单
    main_menu()