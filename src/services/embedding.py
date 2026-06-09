"""
智谱AI Embedding 服务
用于将股票信息向量化，支持语义搜索
"""

import os
import json
import requests
import psycopg2
from typing import List, Optional
import time
from dotenv import load_dotenv

# 加载环境变量
load_dotenv('/home/ubuntu/pilot-agent/.env')

class ZhipuEmbedding:
    """智谱AI Embedding 服务"""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv('ZAI_API_KEY')
        if not self.api_key:
            raise ValueError("请提供 ZAI_API_KEY")
        
        self.base_url = "https://open.bigmodel.cn/api/paas/v4/embeddings"
        self.model = "embedding-3"
        self.dimension = 1024
        
    def get_embedding(self, text: str) -> List[float]:
        """获取单个文本的向量"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.model,
            "input": text,
            "dimensions": self.dimension
        }
        
        try:
            response = requests.post(self.base_url, headers=headers, json=data, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            if 'data' in result and len(result['data']) > 0:
                return result['data'][0]['embedding']
            else:
                raise ValueError(f"API返回异常: {result}")
                
        except Exception as e:
            print(f"获取向量失败: {e}")
            raise
    
    def get_embeddings_batch(self, texts: List[str], batch_size: int = 16) -> List[List[float]]:
        """批量获取文本向量"""
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            data = {
                "model": self.model,
                "input": batch,
                "dimensions": self.dimension
            }
            
            try:
                response = requests.post(self.base_url, headers=headers, json=data, timeout=60)
                response.raise_for_status()
                result = response.json()
                
                if 'data' in result:
                    # 按 index 排序
                    sorted_data = sorted(result['data'], key=lambda x: x['index'])
                    embeddings = [item['embedding'] for item in sorted_data]
                    all_embeddings.extend(embeddings)
                
                # 避免频率限制
                if i + batch_size < len(texts):
                    time.sleep(0.5)
                    
            except Exception as e:
                print(f"批量获取向量失败 (batch {i}): {e}")
                raise
        
        return all_embeddings


class StockVectorDB:
    """股票向量数据库"""
    
    def __init__(self, db_config: dict = None):
        self.db_config = db_config or {
            'host': 'localhost',
            'port': 5432,
            'database': 'stocks_db',
            'user': 'pilot',
            'password': 'pilot123'
        }
        self.conn = None
        
    def connect(self):
        """连接数据库"""
        self.conn = psycopg2.connect(**self.db_config)
        return self.conn
    
    def close(self):
        """关闭连接"""
        if self.conn:
            self.conn.close()
    
    def build_stock_text(self, stock: dict) -> str:
        """构建股票的文本描述，用于生成向量"""
        parts = []
        
        if stock.get('stock_name'):
            parts.append(f"公司名称：{stock['stock_name']}")
        
        if stock.get('stock_code'):
            parts.append(f"证券代码：{stock['stock_code']}")
        
        if stock.get('industry_level1'):
            parts.append(f"所属行业：{stock['industry_level1']}")
        
        if stock.get('industry_level2'):
            parts.append(f"细分行业：{stock['industry_level2']}")
        
        if stock.get('industry_level3'):
            parts.append(f"三级行业：{stock['industry_level3']}")
        
        if stock.get('is_leader') and stock['is_leader'] in ('是', '1'):
            parts.append("该公司是行业龙头")
        
        if stock.get('description'):
            parts.append(f"主营业务：{stock['description']}")
        
        if stock.get('pe_median'):
            pe = stock['pe_median']
            if pe < 0:
                parts.append("当前亏损")
            elif pe < 20:
                parts.append("低估值")
            elif pe < 50:
                parts.append("估值合理")
            else:
                parts.append("高估值")
        
        return "，".join(parts)
    
    def update_embeddings(self, api_key: str = None, batch_size: int = 50):
        """更新所有股票的向量"""
        embedding_service = ZhipuEmbedding(api_key)
        
        conn = self.connect()
        cursor = conn.cursor()
        
        # 获取所有股票
        cursor.execute('''
            SELECT id, stock_code, stock_name, pe_median, pe_percentile,
                   industry_level1, industry_level2, industry_level3,
                   is_leader, description
            FROM stocks
            ORDER BY id
        ''')
        
        columns = ['id', 'stock_code', 'stock_name', 'pe_median', 'pe_percentile',
                   'industry_level1', 'industry_level2', 'industry_level3',
                   'is_leader', 'description']
        
        stocks = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        print(f"📊 共 {len(stocks)} 只股票需要处理")
        
        # 批量处理
        processed = 0
        errors = 0
        
        for i in range(0, len(stocks), batch_size):
            batch = stocks[i:i+batch_size]
            
            # 构建文本
            texts = [self.build_stock_text(stock) for stock in batch]
            
            try:
                # 获取向量
                print(f"⏳ 正在处理 {i+1}-{min(i+batch_size, len(stocks))} ...")
                embeddings = embedding_service.get_embeddings_batch(texts)
                
                # 更新数据库
                for stock, embedding in zip(batch, embeddings):
                    cursor.execute('''
                        UPDATE stocks 
                        SET embedding = %s::vector, updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    ''', (str(embedding), stock['id']))
                
                conn.commit()
                processed += len(batch)
                print(f"✅ 已处理 {processed}/{len(stocks)}")
                
            except Exception as e:
                errors += len(batch)
                print(f"❌ 批次处理失败: {e}")
                conn.rollback()
        
        self.close()
        
        print(f"\n{'='*50}")
        print(f"✅ 向量化完成！")
        print(f"成功: {processed} 条")
        print(f"失败: {errors} 条")
        
        return processed, errors
    
    def search_by_vector(self, query_embedding: List[float], top_k: int = 10) -> List[dict]:
        """向量相似度搜索"""
        conn = self.connect()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT stock_code, stock_name, industry_level1, industry_level2,
                   is_leader, description, pe_median,
                   1 - (embedding <=> %s::vector) as similarity
            FROM stocks
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> %s::vector
            LIMIT %s
        ''', (str(query_embedding), str(query_embedding), top_k))
        
        columns = ['stock_code', 'stock_name', 'industry_level1', 'industry_level2',
                   'is_leader', 'description', 'pe_median', 'similarity']
        
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        self.close()
        
        return results
    
    def search_by_text(self, query: str, api_key: str = None, top_k: int = 10) -> List[dict]:
        """文本语义搜索"""
        embedding_service = ZhipuEmbedding(api_key)
        query_embedding = embedding_service.get_embedding(query)
        return self.search_by_vector(query_embedding, top_k)


if __name__ == '__main__':
    import sys
    
    api_key = os.getenv('ZAI_API_KEY')
    
    if len(sys.argv) < 2:
        print("用法:")
        print("  python embedding.py update  - 更新所有股票向量")
        print("  python embedding.py search <查询文本>  - 语义搜索")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == 'update':
        db = StockVectorDB()
        db.update_embeddings(api_key)
        
    elif command == 'search':
        if len(sys.argv) < 3:
            print("用法: python embedding.py search <查询文本>")
            sys.exit(1)
        
        query = sys.argv[2]
        
        db = StockVectorDB()
        results = db.search_by_text(query, api_key)
        
        print(f"\n🔍 搜索: {query}")
        print("=" * 60)
        for i, r in enumerate(results, 1):
            leader = " [龙头]" if r['is_leader'] in ('是', '1') else ""
            print(f"{i}. {r['stock_code']} {r['stock_name']}{leader}")
            print(f"   行业: {r['industry_level1']} > {r['industry_level2']}")
            print(f"   PE: {r['pe_median']:.2f}" if r['pe_median'] else "   PE: N/A")
            print(f"   相似度: {r['similarity']:.4f}")
            if r['description']:
                print(f"   说明: {r['description'][:50]}...")
            print()
