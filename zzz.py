import requests
from bs4 import BeautifulSoup
import json
import argparse
import os

def extract_pool_data(table, pool_type):
    """从单个卡池表格中提取数据"""
    data = {"type": pool_type}
    
    # 提取卡池名称
    title_th = table.find('th', class_='ys-qy-title')
    if title_th:
        a_tag = title_th.find('a')
        if a_tag and 'title' in a_tag.attrs:
            data['name'] = a_tag['title'].replace('文件:', '').replace('.png', '')
        # 处理图片形式的卡池名称
        else:
            img_tag = title_th.find('img')
            if img_tag and 'alt' in img_tag.attrs:
                data['name'] = img_tag['alt']
    
    # 提取所有行
    rows = table.find_all('tr')
    for row in rows:
        th = row.find('th')
        td = row.find('td')
        if not th or not td:
            continue
            
        header = th.get_text(strip=True)
        if header == '时间':
            data['time'] = td.get_text(strip=True)
        elif header == '版本':
            data['version'] = td.get_text(strip=True)
        elif 'S级' in header:
            # 处理链接和纯文本两种情况
            agents = [a.get_text(strip=True) for a in td.find_all('a')]
            if not agents:
                agents = [span.get_text(strip=True) for span in td.find_all('span')]
            data['up_s'] = agents
        elif 'A级' in header:
            agents = [a.get_text(strip=True) for a in td.find_all('a')]
            if not agents:
                agents = [span.get_text(strip=True) for span in td.find_all('span')]
            data['up_a'] = agents
    
    return data

def get_gacha_data():
    url = "https://wiki.biligame.com/zzz/%E5%BE%80%E6%9C%9F%E8%B0%83%E9%A2%91"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        return {"error": f"请求失败: {str(e)}"}
    
    soup = BeautifulSoup(response.content, 'html.parser')
    all_versions = []
    
    # 找到所有版本标题 (h3标签)
    version_headings = soup.find_all('h3')
    for heading in version_headings:
        # 提取版本信息
        version_span = heading.find('span', class_='mw-headline')
        if not version_span:
            continue
            
        version_title = version_span.get_text(strip=True)
        if '·' in version_title:
            version_number = version_title.split('·')[0].strip()
            phase = "上半" if "第一" in version_title else "下半"
        else:
            continue
        
        # 获取当前版本区块的所有表格
        version_tables = []
        next_element = heading.find_next_sibling()
        while next_element and next_element.name != 'h3':
            if next_element.name == 'table' and 'wikitable' in next_element.get('class', []):
                version_tables.append(next_element)
            next_element = next_element.find_next_sibling()
        
        pools = []
        for table in version_tables:
            # 检查是否是卡池表格组（包含"独家频段"标题）
            if table.find('th', string='独家频段'):
                # 提取角色池和武器池
                character_td = table.find('td')
                weapon_td = table.find_all('td')[1] if len(table.find_all('td')) > 1 else None
                
                if character_td:
                    character_table = character_td.find('table', class_='wikitable')
                    if character_table:
                        pools.append(extract_pool_data(character_table, "character"))
                
                if weapon_td:
                    weapon_table = weapon_td.find('table', class_='wikitable')
                    if weapon_table:
                        pools.append(extract_pool_data(weapon_table, "weapon"))
        
        if pools:
            all_versions.append({
                "version": version_number,
                "phase": phase,
                "pools": pools
            })
    
    # 按版本号排序（从新到旧）
    all_versions.sort(key=lambda x: (
        tuple(map(int, x['version'].split('.'))), 
        0 if x['phase'] == '上半' else 1
    ), reverse=True)
    
    return all_versions

def save_data_to_file():
    """保存数据到文件，只保留最新的6个版本"""
    data = get_gacha_data()
    if 'error' in data:
        print(f"错误: {data['error']}")
        return False
    
    # 只保留最新的6个版本
    latest_versions = data[:6]
    
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(latest_versions, f, ensure_ascii=False, indent=2)
    
    print(f"已保存最新 {len(latest_versions)} 个版本的数据到 data.json")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='绝区零卡池数据抓取工具')
    parser.add_argument('--save', action='store_true', help='将最新的6个版本数据保存到 data.json')
    args = parser.parse_args()
    
    if args.save:
        save_data_to_file()
    else:
        # 本地开发模式
        from flask import Flask, jsonify
        app = Flask(__name__)
        
        @app.route('/api/gacha', methods=['GET'])
        def gacha_api():
            """API端点，返回最新的6个版本卡池信息"""
            gacha_data = get_gacha_data()
            if 'error' in gacha_data:
                return jsonify({"error": gacha_data['error']}), 500
            # 返回最新的6个版本
            return jsonify(gacha_data[:6])
        
        print("启动本地服务器: http://localhost:5000/api/gacha")
        app.run(host='0.0.0.0', port=5000, debug=True)
