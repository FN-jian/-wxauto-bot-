from flask import Flask, request, jsonify
import sqlite3
from datetime import datetime
import threading
import re
import os
import time

app = Flask(__name__)


class TextDB:
    def __init__(self, db_path='knowledge.db'):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.lock = threading.Lock()
        self.keyword_cache = set()  # 关键词缓存
        self.last_refresh = 0
        self._init_db()
        self._refresh_keyword_cache()

    def _init_db(self):
        """初始化数据库表结构"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS knowledge
                           (
                               id
                               INTEGER
                               PRIMARY
                               KEY
                               AUTOINCREMENT,
                               key_text
                               TEXT
                               NOT
                               NULL,
                               content
                               TEXT
                               NOT
                               NULL,
                               created_at
                               TIMESTAMP
                               DEFAULT
                               CURRENT_TIMESTAMP,
                               last_accessed
                               TIMESTAMP,
                               access_count
                               INTEGER
                               DEFAULT
                               0
                           )
                           ''')
            self.conn.commit()

    def _refresh_keyword_cache(self, force=False):
        """刷新关键词缓存"""
        current_time = time.time()
        if force or current_time - self.last_refresh > 3600:  # 每小时刷新一次
            with self.lock:
                cursor = self.conn.cursor()
                cursor.execute('SELECT DISTINCT key_text FROM knowledge')
                self.keyword_cache = {row[0].lower() for row in cursor.fetchall()}
                self.last_refresh = current_time
                print(f"关键词缓存已刷新，当前关键词数量: {len(self.keyword_cache)}")

    def contains_keywords(self, query):
        """检查查询是否包含任何关键词"""
        self._refresh_keyword_cache()
        query_lower = query.lower()
        return any(keyword in query_lower for keyword in self.keyword_cache)

    def add_entry(self, key_text, content):
        """添加知识条目并刷新缓存"""
        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('''
                           INSERT INTO knowledge (key_text, content)
                           VALUES (?, ?)
                           ''', (key_text, content))
            self.conn.commit()
        self._refresh_keyword_cache(force=True)  # 添加后强制刷新缓存
        return True

    def search_entries(self, query, top_n=3):
        """优化版知识检索 - 增强语义匹配"""
        if not self.contains_keywords(query):
            print(f"查询不包含关键词: '{query}'")
            return []

        with self.lock:
            cursor = self.conn.cursor()
            cursor.execute('SELECT id, key_text, content FROM knowledge')
            results = []
            query_lower = query.lower()
            query_words = set(re.findall(r'\w+', query_lower))

            for row in cursor.fetchall():
                id, key_text, content = row
                content_lower = content.lower()
                key_text_lower = key_text.lower()

                # 优化匹配算法
                score = 0

                # 1. 关键词完全匹配
                if key_text_lower in query_lower:
                    score += 5

                # 2. 查询词在关键词中
                if any(word in key_text_lower for word in query_words):
                    score += 4

                # 3. 查询词在内容中
                content_words = set(re.findall(r'\w+', content_lower))
                common_words = query_words & content_words
                score += len(common_words) * 1.5

                # 4. 短语匹配
                for phrase in [key_text_lower] + re.findall(r'\b\w{3,}\b', content_lower):
                    if phrase in query_lower and len(phrase) > 2:
                        score += 3

                if score > 0:
                    results.append({
                        'id': id,
                        'key': key_text,
                        'content': content,
                        'score': score
                    })

        # 按匹配分数排序
        results.sort(key=lambda x: x['score'], reverse=True)

        # 更新访问记录
        with self.lock:
            for item in results[:top_n]:
                cursor.execute('''
                               UPDATE knowledge
                               SET last_accessed=?,
                                   access_count=access_count + 1
                               WHERE id = ?
                               ''', (datetime.now(), item['id']))
            self.conn.commit()

        print(f"找到 {len(results)} 条相关记录，返回前 {min(top_n, len(results))} 条")
        return results[:top_n]


# 初始化数据库
text_db = TextDB()


# API路由
@app.route('/db/add', methods=['POST'])
def add_data():
    data = request.get_json()
    if 'key' not in data or 'content' not in data:
        return jsonify({'status': 'error', 'message': '缺少key或content参数'}), 400

    if text_db.add_entry(data['key'], data['content']):
        return jsonify({'status': 'success'})
    else:
        return jsonify({'status': 'error', 'message': '添加失败'}), 500


@app.route('/db/search', methods=['POST'])
def search_data():
    data = request.get_json()
    if 'query' not in data:
        return jsonify({'status': 'error', 'message': '缺少query参数'}), 400

    results = text_db.search_entries(data['query'])
    return jsonify({'status': 'success', 'data': results})


@app.route('/db/keywords', methods=['GET'])
def list_keywords():
    """获取所有关键词接口"""
    return jsonify({
        'status': 'success',
        'count': len(text_db.keyword_cache),
        'keywords': list(text_db.keyword_cache)
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=6000, threaded=True)