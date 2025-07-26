from flask import Flask, request, jsonify
import requests
import traceback
import os
import time

app = Flask(__name__)

# 配置DeepSeek API密钥
DEEPSEEK_API_KEY = "你的deepseekapi"  # 替换为你的DeepSeek API密钥

# 关键词缓存和刷新机制
keyword_cache = set()
last_keyword_refresh = 0


def refresh_keyword_cache():
    """从数据库服务刷新关键词缓存"""
    global keyword_cache, last_keyword_refresh
    try:
        response = requests.get('http://localhost:6000/db/keywords', timeout=2)
        if response.status_code == 200:
            data = response.json()
            if data['status'] == 'success':
                keyword_cache = set(data['keywords'])
                last_keyword_refresh = time.time()
                print(f"已刷新关键词缓存，当前关键词数量: {len(keyword_cache)}")
    except Exception as e:
        print(f"刷新关键词缓存失败: {str(e)}")


def contains_keywords(question):
    """检查问题是否包含关键词"""
    global keyword_cache, last_keyword_refresh

    # 每小时刷新一次缓存
    if time.time() - last_keyword_refresh > 3600:
        refresh_keyword_cache()

    question_lower = question.lower()
    return any(keyword in question_lower for keyword in keyword_cache)


@app.route('/ai/ask', methods=['POST'])
def ask_question():
    """优化版问答接口 - 智能数据库调用"""
    try:
        data = request.get_json()
        if 'question' not in data:
            return jsonify({'status': 'error', 'message': '缺少question参数'}), 400

        question = data['question']
        print(f"\n===== 收到问题: {question[:50]}{'...' if len(question) > 50 else ''} =====")

        # 智能判断是否需要查询数据库
        knowledge = []
        if contains_keywords(question):
            print("问题包含关键词，正在查询数据库...")
            try:
                db_response = requests.post(
                    "http://localhost:6000/db/search",
                    json={'query': question},
                    timeout=2
                )

                if db_response.status_code == 200:
                    db_data = db_response.json()
                    if db_data['status'] == 'success':
                        knowledge = db_data.get('data', [])
                        print(f"找到 {len(knowledge)} 条相关知识")
                    else:
                        print(f"数据库返回错误: {db_data.get('message', '未知错误')}")
                else:
                    print(f"数据库搜索失败: {db_response.status_code}")
            except Exception as e:
                print(f"数据库请求异常: {str(e)}")
        else:
            print("问题不包含已知关键词，跳过数据库查询")

        # 构建系统提示
        system_prompt = "你是一个知识丰富的AI助手，请根据以下信息回答问题：" #ai人格编辑
        if knowledge:
            system_prompt += "\n\n相关背景：\n" + "\n".join(
                [f"- {item['content']}" for item in knowledge]
            )
        else:
            system_prompt += "\n当前没有相关背景信息，请根据你的知识回答。"

        print(f"系统提示: {system_prompt[:150]}{'...' if len(system_prompt) > 150 else ''}")

        # 调用DeepSeek生成回答
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ]

        try:
            response = requests.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
                json={
                    "model": "deepseek-chat",
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 1000
                },
                timeout=15
            )

            # 检查DeepSeek API响应
            if response.status_code != 200:
                error_msg = f"DeepSeek API错误: {response.status_code}"
                print(error_msg)
                # 尝试使用知识库中的第一条作为回复
                if knowledge:
                    reply = knowledge[0]['content']
                    print(f"使用知识库作为回复")
                    return jsonify({
                        'status': 'success',
                        'reply': reply,
                        'used_knowledge': [item['content'] for item in knowledge],
                        'note': 'Used knowledge directly due to API failure'
                    })
                else:
                    return jsonify({
                        'status': 'error',
                        'message': error_msg
                    }), 500

            response_data = response.json()
            reply = response_data['choices'][0]['message']['content']
            print(f"生成回复: {reply[:100]}{'...' if len(reply) > 100 else ''}")

            return jsonify({
                'status': 'success',
                'reply': reply,
                'used_knowledge': [item['content'] for item in knowledge] if knowledge else [],
                'keywords_used': contains_keywords(question)
            })
        except Exception as e:
            print(f"DeepSeek API调用异常: {str(e)}")
            # 如果调用失败，尝试使用知识库作为回复
            if knowledge:
                reply = knowledge[0]['content']
                print(f"使用知识库作为回复")
                return jsonify({
                    'status': 'success',
                    'reply': reply,
                    'used_knowledge': [item['content'] for item in knowledge],
                    'note': 'Used knowledge directly due to API failure'
                })
            else:
                return jsonify({
                    'status': 'error',
                    'message': f"无法生成回答: {str(e)}"
                }), 500

    except Exception as e:
        error_trace = traceback.format_exc()
        print(f"严重错误: {error_trace}")
        return jsonify({
            'status': 'error',
            'message': str(e),
            'error_type': type(e).__name__,
            'traceback': error_trace
        }), 500


if __name__ == '__main__':
    # 初始化关键词缓存
    refresh_keyword_cache()
    app.run(host='0.0.0.0', port=5000, threaded=True)