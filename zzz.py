import requests
from bs4 import BeautifulSoup
import json
import argparse
import os
import re

def extract_pool_data(table, pool_type):
    """从单个卡池表格中提取数据"""
    data = {"type": pool_type}
    
    # 提取卡池名称 - 处理不同情况
    title_th = table.find('th', class_='ys-qy-title')
    if title_th:
        # 尝试提取链接文本
        a_tag = title_th.find('a')
        if a_tag:
            if a_tag.get('title'):
                data['name'] = a_tag['title'].replace('文件:', '').replace('.png', '').strip()
            else:
                data['name'] = a_tag.get_text(strip=True)
        
        # 尝试提取图片文本
        img_tag = title_th.find('img')
        if img_tag and not data.get('name'):
            if img_tag.get('alt'):
                data['name'] = img_tag['alt'].strip()
            elif img_tag.get('title'):
                data['name'] = img_tag['title'].strip()
    
    # 如果以上方法都失败，直接提取th文本
    if not data.get('name') and title_th:
        data['name'] = title_th.get_text(strip=True)
    
    # 提取所有行
    rows = table.find_all('tr')
    agent_headers = []  # 记录表头信息用于类型判断
    
    for row in rows:
        th = row.find('th')
        td = row.find('td')
        if not th or not td:
            continue
            
        header = th.get_text(strip=True)
        agent_headers.append(header)  # 收集表头信息
        
        # 统一处理S级/A级数据
        if header in ['S级代理人', 'S级音擎']:
            data['up_s'] = extract_agent_data(td)
        elif header in ['A级代理人', 'A级音擎']:
            data['up_a'] = extract_agent_data(td)
        elif header == '时间':
            data['time'] = td.get_text(strip=True)
        elif header == '版本':
            data['version'] = td.get_text(strip=True)
    
    # 优化卡池类型判断逻辑
    # 方法1: 检查表头特征词
    if any("代理人" in h for h in agent_headers):
        data['type'] = "character"
    elif any("音擎" in h for h in agent_headers):
        data['type'] = "weapon"
    # 方法2: 检查卡池名称特征词
    elif 'name' in data:
        if "角色" in data['name'] or "代理人" in data['name']:
            data['type'] = "character"
        elif "音擎" in data['name'] or "武器" in data['name']:
            data['type'] = "weapon"
    # 方法3: 检查UP物品数量特征
    elif len(data.get('up_s', [])) > 1:  # 角色池通常只有一个S级UP
        data['type'] = "weapon"
    
    return data

def extract_agent_data(td):
    """提取代理人和音擎数据，处理不同情况"""
    # 尝试提取链接
    agents = []
    for a in td.find_all('a'):
        agent_text = a.get_text(strip=True)
        if agent_text:
            agents.append(agent_text)
    
    # 如果没有链接，处理纯文本
    if not agents:
        text_content = td.get_text(strip=True)
        # 使用正则表达式提取方括号内的内容
        matches = re.findall(r'\[([^\]]+)\]', text_content)
        if matches:
            agents = matches
        elif text_content:
            # 尝试按换行分割
            lines = [line.strip() for line in text_content.split('\n') if line.strip()]
            if lines:
                agents = lines
            else:
                agents = [text_content]
    
    return agents

def get_gacha_data():
    url = "https://wiki.biligame.com/zzz/%E5%BE%80%E6%9C%9F%E8%B0%83%E9%A2%91"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        return {"error": f"请求失败: {str(e)}"}
    
    soup = BeautifulSoup(response.content, 'html.parser')
    all_versions = []
    
    # 找到所有版本标题 (h3标签)
    version_headings = soup.find_all('h3')
    for heading in version_headings:
        version_span = heading.find('span', class_='mw-headline')
        if not version_span:
            continue
            
        version_title = version_span.get_text(strip=True)
        if '·' in version_title:
            version_number = version_title.split('·')[0].strip()
            # 判断是上半还是下半
            if "第一" in version_title or "上半" in version_title:
                phase = "上半"
            elif "第二" in version_title or "下半" in version_title:
                phase = "下半"
            else:
                phase = "未知"
        else:
            continue
        
        # 获取当前版本区块的所有外层表格
        version_tables = []
        next_element = heading.find_next_sibling()
        while next_element and next_element.name != 'h3':
            # 查找所有wikitable表格（外层表格）
            if next_element.name == 'table' and 'wikitable' in next_element.get('class', []):
                version_tables.append(next_element)
            next_element = next_element.find_next_sibling()
        
        pools = []
        for outer_table in version_tables:
            # 查找所有内嵌的卡池表格
            inner_tables = outer_table.find_all('table', class_='wikitable')
            for inner_table in inner_tables:
                # 检查是否是卡池表格（包含ys-qy-title类）
                if inner_table.find('th', class_='ys-qy-title'):
                    # 初始类型判断（后续会优化）
                    pool_type = "character" if "独家频段" in inner_table.get_text() else "weapon" if "音擎频段" in inner_table.get_text() else "unknown"
                    pools.append(extract_pool_data(inner_table, pool_type))
        
        if pools:
            all_versions.append({
                "version": version_number,
                "phase": phase,
                "pools": pools
            })
    
    # 按版本号排序（从新到旧）
    all_versions.sort(
        key=lambda x: [int(part) for part in x['version'].split('.')],
        reverse=True
    )
    
    return all_versions

def save_data_to_file():
    """保存数据到文件，只保留最新的6个版本"""
    data = get_gacha_data()
    if 'error' in data:
        print(f"错误: {data['error']}")
        return False
    
    # 只保留最新的6个版本
    latest_versions = data[:10]
    
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(latest_versions, f, ensure_ascii=False, indent=2)
    
    print(f"已保存最新 {len(latest_versions)} 个版本的数据到 data.json")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='绝区零卡池数据抓取工具')
    parser.add_argument('--save', action='store_true', help='将数据保存到文件')
    args = parser.parse_args()
    
    if args.save:
        save_data_to_file()
    else:
        # 本地开发模式
        from flask import Flask, jsonify
        app = Flask(__name__)
        
        @app.route('/api/gacha', methods=['GET'])
        def gacha_api():
            """API端点，返回最新的卡池信息"""
            gacha_data = get_gacha_data()
            if isinstance(gacha_data, dict) and 'error' in gacha_data:
                return jsonify({"error": gacha_data['error']}), 500
            # 返回最新的6个版本
            return jsonify(gacha_data[:6])
        
        print("启动本地服务器: http://localhost:5000/api/gacha")
        app.run(host='0.0.0.0', port=5000, debug=True)
