"""测试向量化服务"""

import sys
sys.path.insert(0, '/home/ubuntu/pilot-agent/src/services')

from embedding import ZhipuEmbedding, StockVectorDB

def test_api(api_key: str):
    """测试API连接"""
    print("🧪 测试智谱AI Embedding API...")
    
    try:
        service = ZhipuEmbedding(api_key)
        embedding = service.get_embedding("测试文本")
        print(f"✅ API连接成功！向量维度: {len(embedding)}")
        return True
    except Exception as e:
        print(f"❌ API测试失败: {e}")
        return False

def test_search(api_key: str):
    """测试语义搜索"""
    print("\n🔍 测试语义搜索...")
    
    db = StockVectorDB()
    results = db.search_by_text("军工MLCC龙头", api_key, top_k=5)
    
    print(f"\n搜索结果: '军工MLCC龙头'")
    print("=" * 60)
    for i, r in enumerate(results, 1):
        leader = " [龙头]" if r['is_leader'] in ('是', '1') else ""
        print(f"{i}. {r['stock_code']} {r['stock_name']}{leader}")
        print(f"   行业: {r['industry_level1']} > {r['industry_level2']}")
        print(f"   相似度: {r['similarity']:.4f}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python test_embedding.py <api_key>")
        sys.exit(1)
    
    api_key = sys.argv[1]
    
    if test_api(api_key):
        # 检查是否已有向量数据
        import psycopg2
        conn = psycopg2.connect(
            host='localhost', database='stocks_db',
            user='pilot', password='pilot123'
        )
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM stocks WHERE embedding IS NOT NULL")
        count = cursor.fetchone()[0]
        conn.close()
        
        if count > 0:
            print(f"\n📊 数据库中已有 {count} 条向量数据")
            test_search(api_key)
        else:
            print(f"\n⚠️ 数据库中暂无向量数据，请先运行更新:")
            print(f"   python embedding.py update {api_key}")
