import os
import re
import time
import traceback
import json
from typing import Dict, Any, Optional, List, Tuple
import io
import base64
import hashlib
from datetime import datetime
from pymongo import MongoClient
from bson.objectid import ObjectId
import pandas as pd
import numpy as np
import mysql.connector
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from matplotlib.patches import Circle
import warnings
warnings.filterwarnings('ignore')

# Flask imports
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "revenue_lens")

mongo_client = MongoClient(MONGODB_URI)
mongo_db = mongo_client[MONGO_DB_NAME]
terms_collection = mongo_db["terms_and_conditions"]

# ChromaDB imports
try:
    import chromadb
    from chromadb.config import Settings
    from sentence_transformers import SentenceTransformer
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    print("⚠️  ChromaDB not installed. Install: pip install chromadb sentence-transformers")

# PDF Generation imports
try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.units import inch
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, PageBreak, Table, TableStyle
    from reportlab.lib import colors
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    print("⚠️  ReportLab not installed. PDF generation disabled. Run: pip install reportlab")

# LLM imports
try:
    try:
        from langchain_ollama import OllamaLLM
    except ImportError:
        from langchain_community.llms import Ollama as OllamaLLM
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    print("⚠️  LangChain not installed. Install: pip install langchain-ollama")


# ============= CONFIGURATION =============
CHROMA_PERSIST_DIR = "./chroma_db_results"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

app = Flask(__name__)
CORS(app)

@app.route("/api/legal/terms", methods=["GET"])
def get_terms():
    try:
        doc = terms_collection.find_one({"is_active": True}, sort=[("effective_date", -1)])
        if not doc:
            return jsonify({"success": False, "message": "Terms not found"}), 404

        doc["_id"] = str(doc["_id"])
        return jsonify({"success": True, "terms": doc})
    except Exception as e:
        print("Error fetching terms:", e)
        return jsonify({"success": False, "message": "Failed to load terms"}), 500


# ============= CHROMADB INTEGRATION =============
class ChromaDBResultStore:
    """ChromaDB Manager - Stores SQL query results and insights for report generation"""
    
    def __init__(self, persist_directory: str = CHROMA_PERSIST_DIR):
        if not CHROMADB_AVAILABLE:
            print("⚠️  ChromaDB not available")
            self.enabled = False
            return
            
        print("\n🔵 Initializing ChromaDB Result Store...")
        self.persist_directory = persist_directory
        self.enabled = True
        
        try:
            # Initialize ChromaDB client
            self.client = chromadb.PersistentClient(
                path=persist_directory,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # Initialize embedding model
            self.embedding_model = SentenceTransformer(EMBEDDING_MODEL)
            
            # Single collection for SQL results and insights
            self.results_collection = self._get_or_create_collection("sql_query_results")
            
            print("✅ ChromaDB Result Store initialized\n")
        except Exception as e:
            print(f"❌ ChromaDB initialization failed: {e}")
            self.enabled = False
    
    def _get_or_create_collection(self, name: str):
        """Get or create a collection"""
        try:
            return self.client.get_collection(name=name)
        except:
            return self.client.create_collection(name=name)
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text"""
        return self.embedding_model.encode(text).tolist()
    
    def store_sql_result(self, user_query: str, sql_query: str, 
                         result_df: pd.DataFrame, insights: Dict[str, Any],
                         visualizations: Dict[str, Any], agent_stats: Dict[str, Any]):
        """Store complete SQL query result with insights for report generation"""
        if not self.enabled:
            return None
            
        print("   💾 Storing SQL result in ChromaDB...")
        
        # Create unique ID
        result_id = hashlib.md5(f"{user_query}{datetime.now().isoformat()}".encode()).hexdigest()
        
        # Create comprehensive document for embedding
        document_text = f"""
        Query: {user_query}
        SQL: {sql_query}
        Row Count: {len(result_df)}
        Columns: {', '.join(result_df.columns.tolist())}
        Insights: {' '.join(insights.get('summary', [])[:2])}
        """
        
        embedding = self.generate_embedding(document_text)
        
        # Store complete result data
        metadata = {
            "user_query": user_query,
            "sql_query": sql_query,
            "row_count": len(result_df),
            "columns": json.dumps(result_df.columns.tolist()),
            "timestamp": datetime.now().isoformat(),
            "complexity": agent_stats.get('complexity', 'unknown'),
            "processing_time": agent_stats.get('processing_time', 0),
            "attempts": agent_stats.get('attempts', 1),
            # Store insights for report generation
            "summary": json.dumps(insights.get('summary', [])),
            "insights": json.dumps(insights.get('insights', [])),
            "recommendations": json.dumps(insights.get('strategy', [])),
            # Store sample data (first 10 rows for reference)
            "sample_data": json.dumps(result_df.head(10).to_dict('records')),
            # Visualization metadata
            "has_visualizations": len(visualizations) > 0,
            "visualization_types": json.dumps(list(visualizations.keys()))
        }
        
        self.results_collection.upsert(
            ids=[result_id],
            embeddings=[embedding],
            documents=[document_text],
            metadatas=[metadata]
        )
        
        print(f"   ✅ SQL result stored (ID: {result_id[:8]}...)")
        return result_id
    
    def get_stored_result(self, result_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve stored SQL result by ID"""
        if not self.enabled:
            return None
            
        try:
            results = self.results_collection.get(ids=[result_id])
            if results['ids']:
                metadata = results['metadatas'][0]
                return {
                    'id': result_id,
                    'user_query': metadata['user_query'],
                    'sql_query': metadata['sql_query'],
                    'summary': json.loads(metadata['summary']),
                    'insights': json.loads(metadata['insights']),
                    'recommendations': json.loads(metadata['recommendations']),
                    'sample_data': json.loads(metadata['sample_data']),
                    'columns': json.loads(metadata['columns']),
                    'timestamp': metadata['timestamp'],
                    'complexity': metadata['complexity']
                }
        except Exception as e:
            print(f"   ❌ Error retrieving result: {e}")
        return None
    
    def search_similar_results(self, query: str, n_results: int = 5) -> List[Dict]:
        """Search for similar past SQL results"""
        if not self.enabled:
            return []
            
        print(f"   🔍 Searching for similar results...")
        
        embedding = self.generate_embedding(query)
        
        results = self.results_collection.query(
            query_embeddings=[embedding],
            n_results=n_results
        )
        
        if results['ids'] and results['ids'][0]:
            print(f"   ✅ Found {len(results['ids'][0])} similar results")
            return [{
                'id': results['ids'][0][i],
                'query': results['metadatas'][0][i]['user_query'],
                'sql': results['metadatas'][0][i]['sql_query'],
                'timestamp': results['metadatas'][0][i]['timestamp'],
                'row_count': results['metadatas'][0][i]['row_count'],
                'distance': results['distances'][0][i] if 'distances' in results else None
            } for i in range(len(results['ids'][0]))]
        
        print("   ℹ️ No similar results found")
        return []
    
    def get_all_stored_queries(self, limit: int = 50) -> List[Dict]:
        """Get all stored queries for history/reference"""
        if not self.enabled:
            return []
            
        try:
            results = self.results_collection.get(limit=limit)
            return [{
                'id': results['ids'][i],
                'query': results['metadatas'][i]['user_query'],
                'timestamp': results['metadatas'][i]['timestamp'],
                'complexity': results['metadatas'][i]['complexity']
            } for i in range(len(results['ids']))]
        except Exception as e:
            print(f"   ❌ Error getting query history: {e}")
            return []


# ============= SCHEMA EXTRACTION =============
def _fetch_mysql_schema(db_cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Fetch table/column info from MySQL information_schema with sample data."""
    conn = mysql.connector.connect(
        host=db_cfg.get("host", "localhost"),
        user=db_cfg.get("user"),
        password=db_cfg.get("password", ""),
        database=db_cfg.get("database"),
        port=int(db_cfg.get("port", 3306)),
    )
    cur = conn.cursor(dictionary=True)
    cur.execute(
        "SELECT TABLE_NAME FROM information_schema.tables "
        "WHERE table_schema=%s ORDER BY TABLE_NAME",
        (db_cfg.get("database"),),
    )
    tables = [r["TABLE_NAME"] for r in cur.fetchall()]
    schema: Dict[str, Any] = {}
    
    for t in tables:
        cur.execute(
            """
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_TYPE
            FROM information_schema.columns
            WHERE table_schema=%s AND table_name=%s
            ORDER BY ORDINAL_POSITION
            """,
            (db_cfg.get("database"), t),
        )
        cols = cur.fetchall()
        
        try:
            cur.execute(f"SELECT COUNT(*) AS cnt FROM `{t}`")
            rc = cur.fetchone().get("cnt", 0)
        except Exception:
            rc = 0
        
        sample_data = []
        try:
            cur.execute(f"SELECT * FROM `{t}` LIMIT 3")
            sample_data = cur.fetchall()
        except Exception:
            pass
        
        schema[t] = {
            "columns": [c["COLUMN_NAME"] for c in cols],
            "dtypes": {c["COLUMN_NAME"]: c["DATA_TYPE"] for c in cols},
            "nullable": {c["COLUMN_NAME"]: c["IS_NULLABLE"] for c in cols},
            "column_type": {c["COLUMN_NAME"]: c["COLUMN_TYPE"] for c in cols},
            "row_count": int(rc),
            "sample_data": sample_data[:3]
        }
    
    cur.close()
    conn.close()
    return schema


def _schema_to_text(schema: Dict[str, Any]) -> str:
    """Convert schema dict into a detailed human-readable text block."""
    lines = ["=== DATABASE SCHEMA ===", ""]
    for t, info in schema.items():
        cols = info.get("columns", [])
        dtypes = info.get("dtypes", {})
        sample_data = info.get("sample_data", [])
        
        lines.append(f"TABLE: {t}  (Total rows: {info.get('row_count', 0)})")
        lines.append("Columns:")
        for c in cols:
            lines.append(f"  - {c} ({dtypes.get(c, 'unknown')})")
        
        if sample_data:
            lines.append("Sample data (first 2 rows):")
            for i, row in enumerate(sample_data[:2], 1):
                lines.append(f"  Row {i}: {dict(row)}")
        
        lines.append("")
    
    return "\n".join(lines)


# ============= SQL EXTRACTION & VALIDATION =============
def _extract_sql(text: str) -> Optional[str]:
    """Extract SQL SELECT statement from LLM output - FIXED VERSION."""
    if not text:
        return None
    
    # Pattern 1: ```sql ... ```
    m = re.search(r"```sql\s*(.*?)\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if m:
        sql = m.group(1).strip().rstrip(";")
        return sql
    
    # Pattern 2: ``` SELECT ... ```
    m = re.search(r"```\s*(SELECT[\s\S]+?)```", text, flags=re.IGNORECASE)
    if m:
        sql = m.group(1).strip().rstrip(";")
        return sql
    
    # Pattern 3: Look for SELECT without code blocks - IMPROVED
    # Find all SELECT statements and take the complete one
    select_pattern = r'SELECT\s+.+?\s+FROM\s+.+?(?:WHERE\s+.+?)?(?:GROUP\s+BY\s+.+?)?(?:ORDER\s+BY\s+.+?)?(?:LIMIT\s+.+?)?(?=;|\n\n|$)'
    matches = re.findall(select_pattern, text, re.IGNORECASE | re.DOTALL)
    
    if matches:
        # Take the longest match (likely the complete query)
        sql = max(matches, key=len).strip().rstrip(";")
        return sql
    
    # Pattern 4: Simple fallback - get everything from SELECT onwards
    if 'SELECT' in text.upper():
        idx = text.upper().index('SELECT')
        sql = text[idx:].strip().rstrip(";")
        # Remove any trailing explanation text
        sql = re.sub(r'\n\n.*$', '', sql, flags=re.DOTALL)
        return sql.strip()
    
    return None


# ============= AGENTIC SQL ENGINE =============
class AgenticSQLEngine:
    """Agentic AI Engine - Self-correcting SQL generation with intelligent retry"""
    
    def __init__(self, llm, schema_info: str):
        self.llm = llm
        self.schema_info = schema_info
        print("🤖 Agentic SQL Engine initialized")
    
    def analyze_error_and_decide_fix(self, sql_query: str, error: str, attempt: int) -> Dict[str, Any]:
        """Agentic AI analyzes error and decides correction strategy"""
        print(f"\n   🤖 Agentic AI analyzing error (attempt {attempt})...")
        
        prompt = f"""You are an AI agent that fixes SQL errors intelligently.

FAILED SQL:
{sql_query}

ERROR MESSAGE:
{error}

ATTEMPT: {attempt}

Analyze the error and provide a fix strategy. Common issues:
1. Table doesn't exist → Check table name spelling
2. Column doesn't exist → Verify column names
3. Syntax error → Fix SQL syntax
4. Ambiguous column → Add table aliases
5. JOIN issues → Verify foreign key relationships

Respond ONLY in JSON format:
{{
  "error_type": "table_not_found|column_not_found|syntax_error|join_error|other",
  "root_cause": "Brief explanation",
  "fix_strategy": "Specific fix to apply",
  "confidence": "high|medium|low"
}}"""

        try:
            response = self.llm.invoke(prompt)
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                decision = json.loads(json_match.group())
                print(f"   ✅ Fix Strategy: {decision['fix_strategy'][:80]}...")
                return decision
        except Exception as e:
            print(f"   ⚠️ Failed to parse AI decision: {e}")
        
        # Default fallback strategy
        return {
            "error_type": "unknown",
            "root_cause": "Unable to determine",
            "fix_strategy": "Regenerate SQL with error context",
            "confidence": "low"
        }
    
    def generate_sql_with_retry(self, user_query: str, max_attempts: int = 8, 
                                mysql_config: Dict[str, Any] = None) -> Tuple[Optional[str], Dict[str, Any]]:
        """Generate SQL with agentic self-correction"""
        print(f"\n🤖 AGENTIC SQL GENERATION: {user_query}")
        
        sql_query = None
        error_history = []
        fix_strategies = []
        
        for attempt in range(1, max_attempts + 1):
            print(f"\n   📍 Attempt {attempt}/{max_attempts}")
            
            # Build prompt with error context if retrying
            error_context = ""
            if attempt > 1 and error_history:
                # Agentic decision on how to fix
                fix_decision = self.analyze_error_and_decide_fix(
                    sql_query, error_history[-1], attempt
                )
                fix_strategies.append(fix_decision)
                
                error_context = f"""
PREVIOUS ERROR:
{error_history[-1]}

AI FIX STRATEGY:
{fix_decision['fix_strategy']}

APPLY THIS FIX NOW!
"""
            
            # Generate SQL
            sql_query = self._generate_sql_prompt(user_query, error_context, attempt)
            
            if not sql_query:
                print("   ❌ Failed to generate SQL")
                continue
            
            # Print FULL SQL query for debugging
            print(f"   💻 Generated FULL SQL:\n{sql_query}")
            
            # Validate SQL by executing
            if mysql_config:
                is_valid, error = self._validate_sql(sql_query, mysql_config)
                
                if is_valid:
                    print(f"   ✅ SUCCESS! Valid SQL generated")
                    stats = {
                        'attempts': attempt,
                        'errors': len(error_history),
                        'fix_strategies': fix_strategies,
                        'success': True
                    }
                    return sql_query, stats
                else:
                    print(f"   ❌ SQL Error: {error[:200]}...")
                    error_history.append(error)
            else:
                # No validation, assume success
                stats = {
                    'attempts': attempt,
                    'errors': 0,
                    'fix_strategies': [],
                    'success': True
                }
                return sql_query, stats
        
        print(f"   ❌ Failed after {max_attempts} attempts")
        stats = {
            'attempts': max_attempts,
            'errors': len(error_history),
            'fix_strategies': fix_strategies,
            'success': False
        }
        return None, stats
    
    def _generate_sql_prompt(self, user_query: str, error_context: str, attempt: int) -> Optional[str]:
        """Generate SQL using AI with adaptive prompting"""
        
        prompt = f"""You are an expert MySQL analyst. Generate PRECISE SQL.

{self.schema_info[:2500]}

USER QUERY: "{user_query}"

CRITICAL RULES:
1. Use EXACT table names from schema above
2. Use EXACT column names from schema above
3. Use table aliases: products AS p, sales AS s, customers AS c
4. Always fully qualify columns in JOINs: p.column_name, s.column_name
5. For "top N" queries: Add ORDER BY DESC and LIMIT N
6. Column names are case-sensitive: use exact names from schema
7. Verify all columns exist in their respective tables
8. Use proper JOIN syntax with ON clauses
9. For revenue calculations: price × quantity
10. COMPLETE the entire SQL query - do not truncate

{error_context}

Return ONLY the COMPLETE SQL query. NO truncation. NO explanations.

SQL:"""
        
        try:
            response = self.llm.invoke(prompt)
            extracted_sql = _extract_sql(response)
            
            # Double-check we got the complete query
            if extracted_sql and 'JOIN' in extracted_sql.upper():
                # Ensure JOIN clause is complete
                if extracted_sql.endswith('JOI') or extracted_sql.endswith('JOIN'):
                    print(f"   ⚠️ Detected truncated SQL, requesting complete version...")
                    # Try again with explicit instruction
                    retry_prompt = f"{prompt}\n\nIMPORTANT: Provide the COMPLETE SQL query including all JOIN clauses. Previous attempt was truncated."
                    response = self.llm.invoke(retry_prompt)
                    extracted_sql = _extract_sql(response)
            
            return extracted_sql
        except Exception as e:
            print(f"   ❌ LLM error: {e}")
            return None
    
    def _validate_sql(self, sql_query: str, mysql_config: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate SQL by attempting dry-run"""
        try:
            conn = mysql.connector.connect(**mysql_config)
            cursor = conn.cursor()
            
            # Try to execute
            cursor.execute(sql_query)
            cursor.fetchall()  # Consume results
            
            cursor.close()
            conn.close()
            return True, None
            
        except mysql.connector.Error as e:
            return False, str(e)
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"


# ============= QUERY COMPLEXITY ASSESSMENT =============
def _assess_query_complexity(user_query: str) -> Tuple[str, int]:
    """Assess query complexity and determine max retry attempts."""
    query_lower = user_query.lower()
    
    complex_keywords = ['join', 'subquery', 'nested', 'complex', 'multiple tables', 
                        'aggregate', 'group by', 'having', 'window function']
    moderate_keywords = ['where', 'filter', 'sort', 'order by', 'top', 'limit']
    
    complex_count = sum(1 for kw in complex_keywords if kw in query_lower)
    moderate_count = sum(1 for kw in moderate_keywords if kw in query_lower)
    
    if complex_count >= 2:
        return "high", 8
    elif complex_count >= 1 or moderate_count >= 2:
        return "medium", 6
    else:
        return "simple", 4


# ============= DATAFRAME ANALYSIS - FIXED VERSION =============
def _analyze_dataframe(df: pd.DataFrame) -> Dict[str, Any]:
    """Analyze DataFrame with AGGRESSIVE categorical detection."""
    analysis = {
        "datetime_cols": [],
        "numeric_cols": [],
        "categorical_cols": [],
        "text_cols": [],
        "binary_cols": [],
        "geo_cols": {"lat": None, "lon": None},
        "row_count": len(df),
        "col_count": len(df.columns),
        "recommended_charts": []
    }
    
    if df.empty:
        return analysis
    
    print(f"\n   🔍 Analyzing DataFrame: {df.shape}")
    
    for col in df.columns:
        dtype_str = str(df[col].dtype)
        n_unique = df[col].nunique(dropna=True)
        
        print(f"   - {col}: dtype={dtype_str}, unique={n_unique}, total={len(df)}")
        
        # DateTime detection
        if dtype_str.startswith("datetime") or pd.api.types.is_datetime64_any_dtype(df[col]):
            analysis["datetime_cols"].append(col)
            print(f"     ✓ Classified as DATETIME")
        
        # Numeric detection
        elif pd.api.types.is_numeric_dtype(df[col]):
            analysis["numeric_cols"].append(col)
            print(f"     ✓ Classified as NUMERIC")
            
            if n_unique <= 2:
                analysis["binary_cols"].append(col)
        
        # AGGRESSIVE Categorical detection
        elif dtype_str == 'object' or pd.api.types.is_string_dtype(df[col]):
            # NEW: If every value is unique (like customer names), still treat as categorical
            # This allows for COUNT-based visualizations
            if n_unique == len(df) and len(df) <= 50:
                # Treat as categorical for small datasets
                analysis["categorical_cols"].append(col)
                print(f"     ✓ Classified as CATEGORICAL (all unique, small dataset)")
            elif n_unique <= max(100, int(len(df) * 0.9)):
                # Original logic - up to 90% unique
                analysis["categorical_cols"].append(col)
                print(f"     ✓ Classified as CATEGORICAL")
            else:
                analysis["text_cols"].append(col)
                print(f"     ✓ Classified as TEXT")
        
        # Geospatial detection
        col_lower = col.lower()
        if "lat" in col_lower or "latitude" in col_lower:
            analysis["geo_cols"]["lat"] = col
        if "lon" in col_lower or "lng" in col_lower or "longitude" in col_lower:
            analysis["geo_cols"]["lon"] = col
    
    # FORCE chart recommendations
    if analysis["categorical_cols"] or df.columns.size >= 2:
        analysis["recommended_charts"].extend(["bar", "pie"])
    
    if analysis["numeric_cols"]:
        analysis["recommended_charts"].append("histogram")
    
    if analysis["datetime_cols"] and analysis["numeric_cols"]:
        analysis["recommended_charts"].append("line")
    
    if len(analysis["numeric_cols"]) >= 2:
        analysis["recommended_charts"].append("scatter")
    
    print(f"   ✓ Analysis complete:")
    print(f"     Numeric: {analysis['numeric_cols']}")
    print(f"     Categorical: {analysis['categorical_cols']}")
    print(f"     Recommended: {analysis['recommended_charts']}")
    
    return analysis


# ============= VISUALIZATION GENERATION - FIXED VERSION =============
def _fig_to_base64(fig) -> str:
    """Convert matplotlib figure to base64 string."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches='tight', facecolor='white')
    buf.seek(0)
    img_bytes = buf.read()
    buf.close()
    plt.close(fig)
    return base64.b64encode(img_bytes).decode("utf-8")


def _create_pie_chart(df: pd.DataFrame, category_col: str, value_col: str, 
                     title: str = None) -> Optional[str]:
    """Create pie chart with value aggregation."""
    try:
        plt.close("all")
        fig, ax = plt.subplots(figsize=(10, 8))
        
        # Aggregate values by category
        agg_df = df.groupby(category_col)[value_col].sum().reset_index()
        
        if len(agg_df) > 10:
            # Top 10 + Others
            top_10 = agg_df.nlargest(10, value_col)
            others_sum = agg_df[~agg_df[category_col].isin(top_10[category_col])][value_col].sum()
            if others_sum > 0:
                others_row = pd.DataFrame({category_col: ['Others'], value_col: [others_sum]})
                agg_df = pd.concat([top_10, others_row], ignore_index=True)
            else:
                agg_df = top_10
        
        colors_arr = plt.cm.Set3(range(len(agg_df)))
        wedges, texts, autotexts = ax.pie(
            agg_df[value_col].values,
            labels=agg_df[category_col].values,
            autopct='%1.1f%%',
            startangle=90,
            colors=colors_arr,
            textprops={'fontsize': 10, 'weight': 'bold'},
            explode=[0.05] * len(agg_df)
        )
        
        for autotext in autotexts:
            autotext.set_color('white')
        
        ax.set_title(title or f"{value_col} Distribution by {category_col}",
                    fontsize=14, fontweight='bold', pad=20)
        
        plt.tight_layout()
        return _fig_to_base64(fig)
        
    except Exception as e:
        print(f"   ❌ Pie chart error: {e}")
        traceback.print_exc()
        return None


def _create_pie_chart_count(df: pd.DataFrame, category_col: str, 
                           title: str = None) -> Optional[str]:
    """Create pie chart based on category counts."""
    try:
        plt.close("all")
        fig, ax = plt.subplots(figsize=(10, 8))
        
        # Count occurrences
        counts = df[category_col].value_counts()
        
        if len(counts) > 10:
            # Top 10 + Others
            top_10 = counts.head(10)
            others_sum = counts[10:].sum()
            if others_sum > 0:
                counts = pd.concat([top_10, pd.Series({'Others': others_sum})])
            else:
                counts = top_10
        
        colors_arr = plt.cm.Set3(range(len(counts)))
        wedges, texts, autotexts = ax.pie(
            counts.values,
            labels=counts.index,
            autopct='%1.1f%%',
            startangle=90,
            colors=colors_arr,
            textprops={'fontsize': 10, 'weight': 'bold'},
            explode=[0.05] * len(counts)
        )
        
        for autotext in autotexts:
            autotext.set_color('white')
        
        ax.set_title(title or f"{category_col} Distribution (Count)",
                    fontsize=14, fontweight='bold', pad=20)
        
        plt.tight_layout()
        return _fig_to_base64(fig)
        
    except Exception as e:
        print(f"   ❌ Count pie chart error: {e}")
        traceback.print_exc()
        return None


def _create_bar_chart(df: pd.DataFrame, x_col: str, y_col: str, title: str = None) -> Optional[str]:
    """Create a bar chart visualization."""
    try:
        plt.close("all")
        fig, ax = plt.subplots(figsize=(12, 7))
        
        agg_df = df.groupby(x_col)[y_col].sum().reset_index()
        
        if len(agg_df) > 20:
            agg_df = agg_df.nlargest(20, y_col)
        
        colors_arr = plt.cm.viridis(np.linspace(0.3, 0.9, len(agg_df)))
        bars = ax.bar(range(len(agg_df)), agg_df[y_col], color=colors_arr, edgecolor='black', linewidth=1.2)
        
        ax.set_xticks(range(len(agg_df)))
        ax.set_xticklabels(agg_df[x_col], rotation=45, ha='right', fontsize=10)
        ax.set_xlabel(x_col, fontsize=12, fontweight='bold')
        ax.set_ylabel(y_col, fontsize=12, fontweight='bold')
        ax.set_title(title or f"{y_col} by {x_col}", fontsize=14, fontweight='bold', pad=20)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:,.0f}',
                    ha='center', va='bottom', fontsize=9)
        
        plt.tight_layout()
        return _fig_to_base64(fig)
    except Exception as e:
        print(f"   ❌ Bar chart error: {e}")
        traceback.print_exc()
        return None


def _create_bar_chart_count(df: pd.DataFrame, category_col: str,
                            title: str = None) -> Optional[str]:
    """Create bar chart based on category counts."""
    try:
        plt.close("all")
        fig, ax = plt.subplots(figsize=(12, 7))
        
        # Count occurrences
        counts = df[category_col].value_counts().head(20)
        
        colors_arr = plt.cm.viridis(np.linspace(0.3, 0.9, len(counts)))
        bars = ax.bar(range(len(counts)), counts.values, 
                     color=colors_arr, edgecolor='black', linewidth=1.2)
        
        ax.set_xticks(range(len(counts)))
        ax.set_xticklabels(counts.index, rotation=45, ha='right')
        ax.set_ylabel('Count', fontsize=12, fontweight='bold')
        ax.set_title(title or f"Count by {category_col}",
                    fontsize=14, fontweight='bold', pad=20)
        ax.grid(axis='y', alpha=0.3)
        
        # Add value labels
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{int(height)}', ha='center', va='bottom')
        
        plt.tight_layout()
        return _fig_to_base64(fig)
        
    except Exception as e:
        print(f"   ❌ Count bar chart error: {e}")
        traceback.print_exc()
        return None


def _create_line_chart(df: pd.DataFrame, x_col: str, y_col: str, title: str = None) -> Optional[str]:
    """Create a line chart for time series data."""
    try:
        plt.close("all")
        fig, ax = plt.subplots(figsize=(12, 7))
        
        df_sorted = df.sort_values(by=x_col).copy()
        
        ax.plot(df_sorted[x_col], df_sorted[y_col], marker='o', linewidth=2.5, 
                markersize=6, color='#2563eb', markerfacecolor='#60a5fa',
                markeredgecolor='white', markeredgewidth=1.5)
        
        ax.set_xlabel(x_col, fontsize=12, fontweight='bold')
        ax.set_ylabel(y_col, fontsize=12, fontweight='bold')
        ax.set_title(title or f"{y_col} Trend Over {x_col}", fontsize=14, fontweight='bold', pad=20)
        ax.grid(True, alpha=0.3, linestyle='--')
        
        if len(df_sorted) > 10:
            plt.xticks(rotation=45, ha='right')
        
        plt.tight_layout()
        return _fig_to_base64(fig)
    except Exception as e:
        print(f"   ❌ Line chart error: {e}")
        traceback.print_exc()
        return None


# ============= PROFESSIONAL ANALYSIS ENGINE =============
def _build_rich_narrative(llm, schema_text: str, user_query: str, sql: str, df: pd.DataFrame) -> Dict[str, Any]:
    """Generate insights using LLM based on query results."""
    preview_rows = df.head(10).to_dict(orient="records") if not df.empty else []
    stats = df.describe(include="all").to_dict() if not df.empty else {}

    prompt = f"""You are a senior data analyst. Analyze the query results and provide insights in JSON format.

DATABASE SCHEMA:
{schema_text}

USER QUERY:
{user_query}

SQL EXECUTED:
{sql}

DATA PREVIEW (first 10 rows):
{preview_rows}

STATISTICS:
{stats}

Generate a JSON response with these 3 keys:
1. "summary": 2-3 bullet points describing what the data shows
2. "insights": 2-4 key findings and patterns in the data
3. "strategy": 2-3 actionable recommendations

Requirements:
- Each bullet should be a complete sentence
- Include specific numbers and percentages
- Use Indian Rupees (₹) for all currency values, not dollars ($)
- Focus on business value
- NO markdown, numbering, or special characters
- Return ONLY valid JSON

Example:
{{
  "summary": ["Dataset contains 150 records across 5 categories", "Total revenue is ₹2.5 Cr with average of ₹1,66,667"],
  "insights": ["Electronics leads with 45% of revenue", "Q4 sales increased 23% vs Q3", "Customer retention at 67%"],
  "strategy": ["Focus marketing on top Electronics category", "Replicate Q4 success factors", "Implement loyalty program"]
}}

Your JSON:"""

    try:
        raw = llm.invoke(prompt)
        raw = raw.strip()
        
        if raw.startswith("```json"):
            raw = raw[7:]
        if raw.startswith("```"):
            raw = raw[3:]
        if raw.endswith("```"):
            raw = raw[:-3]
        raw = raw.strip()
        
        parsed = json.loads(raw)
        
        return {
            "summary": parsed.get("summary", []),
            "insights": parsed.get("insights", []),
            "strategy": parsed.get("strategy", [])
        }
    except Exception as e:
        print(f"Narrative generation error: {e}")
        # Fallback to basic analysis
        return _generate_basic_narrative(df, user_query)


def _generate_basic_narrative(df: pd.DataFrame, user_query: str) -> Dict[str, Any]:
    """Generate basic narrative without LLM"""
    analysis = {
        'summary': [],
        'insights': [],
        'strategy': []
    }
    
    if df.empty:
        analysis['summary'].append("No data found matching the query criteria.")
        return analysis
    
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    categorical_cols = df.select_dtypes(include=['object']).columns.tolist()
    
    # Summary
    analysis['summary'].append(
        f"Query returned {len(df)} rows with {len(df.columns)} columns from the database."
    )
    
    if numeric_cols:
        metric_col = numeric_cols[-1]
        total = df[metric_col].sum()
        mean = df[metric_col].mean()
        analysis['summary'].append(
            f"Total {metric_col}: {total:,.2f} with average of {mean:,.2f} per record."
        )
    
    # Insights
    if categorical_cols and numeric_cols:
        cat_col = categorical_cols[0]
        num_col = numeric_cols[-1]
        
        top_3 = df.nlargest(3, num_col)
        if len(top_3) > 0:
            top_val = top_3.iloc[0]
            analysis['insights'].append(
                f"Top performer: {top_val[cat_col]} with {num_col} of {top_val[num_col]:,.2f}"
            )
    
    # Strategy
    analysis['strategy'].append(
        "Analyze top performers to identify success factors and replicate across organization."
    )
    
    return analysis


# ============= PDF REPORT GENERATION - ENHANCED =============
def _generate_pdf_report(output_path: str, user_query: str, sql: str, df: pd.DataFrame,
                         narrative: Dict[str, Any], visualizations: Dict[str, Any]) -> bool:
    """Generate a professional PDF report with ALL visualizations properly embedded."""
    if not PDF_AVAILABLE:
        print("⚠️  PDF generation skipped - ReportLab not installed")
        return False
    
    try:
        print(f"\n📄 Generating PDF Report: {output_path}")
        
        doc = SimpleDocTemplate(output_path, pagesize=letter, 
                               topMargin=0.75*inch, bottomMargin=0.75*inch,
                               leftMargin=0.75*inch, rightMargin=0.75*inch)
        story = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1e3a8a'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#2563eb'),
            spaceAfter=12,
            spaceBefore=20,
            fontName='Helvetica-Bold'
        )
        
        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['BodyText'],
            fontSize=11,
            spaceAfter=10,
            leading=16
        )
        
        bullet_style = ParagraphStyle(
            'BulletStyle',
            parent=styles['BodyText'],
            fontSize=10,
            leftIndent=20,
            spaceAfter=8,
            leading=14
        )
        
        # Title
        story.append(Paragraph("📊 Agentic AI Analytics Report", title_style))
        story.append(Spacer(1, 0.3*inch))
        
        # Query Section
        story.append(Paragraph("🔍 Analysis Query", heading_style))
        story.append(Paragraph(user_query, body_style))
        story.append(Spacer(1, 0.2*inch))
        
        # SQL Section - FIXED to show complete SQL
        story.append(Paragraph("💻 SQL Query", heading_style))
        sql_formatted = sql.replace('\n', '<br/>').replace(' ', '&nbsp;')
        # Limit SQL display to avoid overflow
        if len(sql_formatted) > 1000:
            sql_formatted = sql_formatted[:1000] + '...'
        sql_para = Paragraph(f'<font name="Courier" size="8">{sql_formatted}</font>', body_style)
        story.append(sql_para)
        story.append(Spacer(1, 0.2*inch))
        
        # Results Summary
        story.append(Paragraph("📈 Results Summary", heading_style))
        summary_text = f"Retrieved <b>{len(df)}</b> rows and <b>{len(df.columns)}</b> columns"
        story.append(Paragraph(summary_text, body_style))
        story.append(Spacer(1, 0.2*inch))
        
        # Summary Points
        if narrative.get("summary"):
            story.append(Paragraph("📋 Key Findings", heading_style))
            for point in narrative["summary"]:
                story.append(Paragraph(f"• {point}", bullet_style))
            story.append(Spacer(1, 0.2*inch))
        
        # CRITICAL FIX: Visualizations - Ensure ALL charts are included
        chart_order = visualizations.get("chart_order", [])
        if chart_order:
            story.append(PageBreak())
            story.append(Paragraph("📊 Data Visualizations", heading_style))
            story.append(Spacer(1, 0.1*inch))
            
            print(f"   📊 Adding {len(chart_order)} visualizations to PDF...")
            
            for i, chart_type in enumerate(chart_order):
                if chart_type in visualizations:
                    chart_data = visualizations[chart_type]
                    
                    # Chart title
                    chart_title = chart_data.get("title", chart_type.title())
                    story.append(Paragraph(chart_title, ParagraphStyle(
                        'ChartTitle',
                        parent=styles['Heading3'],
                        fontSize=13,
                        textColor=colors.HexColor('#4338ca'),
                        spaceAfter=8,
                        fontName='Helvetica-Bold'
                    )))
                    
                    # Chart description
                    if chart_data.get("description"):
                        story.append(Paragraph(chart_data["description"], ParagraphStyle(
                            'ChartDesc',
                            parent=styles['BodyText'],
                            fontSize=9,
                            textColor=colors.grey,
                            spaceAfter=10,
                            fontStyle='italic'
                        )))
                    
                    # Add image - CRITICAL FIX
                    img_data = chart_data.get("base64") or chart_data.get("image")
                    if img_data:
                        try:
                            img_bytes = base64.b64decode(img_data)
                            img_buffer = io.BytesIO(img_bytes)
                            
                            img = RLImage(img_buffer, width=6*inch, height=3.5*inch)
                            story.append(img)
                            story.append(Spacer(1, 0.3*inch))
                            
                            print(f"      ✅ Added {chart_type} chart to PDF")
                        except Exception as e:
                            print(f"      ❌ Failed to add {chart_type} chart: {e}")
                    else:
                        print(f"      ⚠️ No image data for {chart_type}")
                    
                    # Page break after every 2 charts
                    if (i + 1) % 2 == 0 and i < len(chart_order) - 1:
                        story.append(PageBreak())
        else:
            print("   ⚠️ No visualizations to add to PDF")
        
        # Insights
        if narrative.get("insights"):
            story.append(PageBreak())
            story.append(Paragraph("💡 Key Insights", heading_style))
            for insight in narrative["insights"]:
                story.append(Paragraph(f"• {insight}", bullet_style))
            story.append(Spacer(1, 0.2*inch))
        
        # Strategy/Recommendations
        if narrative.get("strategy"):
            story.append(Paragraph("🎯 Recommended Actions", heading_style))
            for action in narrative["strategy"]:
                story.append(Paragraph(f"• {action}", bullet_style))
            story.append(Spacer(1, 0.2*inch))
        
        # Data Table (first 20 rows)
        if not df.empty:
            story.append(PageBreak())
            story.append(Paragraph("📄 Data Preview (First 20 Rows)", heading_style))
            story.append(Spacer(1, 0.1*inch))
            
            # Prepare table data
            table_data = [df.columns.tolist()]
            for _, row in df.head(20).iterrows():
                table_data.append([str(val)[:50] for val in row.values])
            
            # Create table
            col_widths = [6.5*inch / len(df.columns)] * len(df.columns)
            t = Table(table_data, colWidths=col_widths, repeatRows=1)
            
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563eb')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f3f4f6')])
            ]))
            
            story.append(t)
            
            if len(df) > 20:
                story.append(Spacer(1, 0.1*inch))
                story.append(Paragraph(f"<i>Showing first 20 of {len(df)} rows</i>", 
                                     ParagraphStyle('Note', parent=styles['BodyText'], 
                                                  fontSize=9, textColor=colors.grey)))
        
        # Build PDF
        doc.build(story)
        print(f"   ✅ PDF report generated successfully: {output_path}\n")
        return True
        
    except Exception as e:
        print(f"\n❌ PDF generation failed: {e}")
        traceback.print_exc()
        return False


# ============= MAIN ANALYTICS FUNCTION =============
def run_langgraph_analytics(mysql_config: Dict[str, Any], user_query: str, 
                           generate_pdf: bool = False, pdf_output: str = None,
                           use_agentic: bool = True, chroma_store: Optional[ChromaDBResultStore] = None) -> Dict[str, Any]:
    """Main analytics pipeline with enhanced visualizations, insights, and ChromaDB integration.
    
    Args:
        mysql_config: Dict with host, user, password, database, port
        user_query: Natural language query
        generate_pdf: Whether to generate a PDF report
        pdf_output: Path for PDF output (default: analytics_report_<timestamp>.pdf)
        use_agentic: Use agentic SQL generation with retry logic
        chroma_store: Optional ChromaDB store instance
        
    Returns:
        Dict with SQL, data, visualizations, insights, and stats
    """
    start_time = time.time()
    
    print("\n" + "="*60)
    print("🚀 AGENTIC AI ANALYTICS STARTING")
    print("="*60)
    
    # Validate config
    host = mysql_config.get("host", "localhost")
    user = mysql_config.get("user")
    password = mysql_config.get("password", "")
    database = mysql_config.get("database")
    port = int(mysql_config.get("port", 3306))

    if not user or not database:
        return {
            "error": "mysql_config must include 'user' and 'database'",
            "success": False
        }

    if not user_query or not user_query.strip():
        return {
            "error": "user_query is required",
            "success": False
        }

    try:
        # Step 1: Assess query complexity
        complexity, max_retries = _assess_query_complexity(user_query)
        print(f"\n📋 Query: {user_query}")
        print(f"🔍 Complexity: {complexity} (max retries: {max_retries})")
        
        # Step 2: Fetch schema
        print(f"\n📚 Fetching schema from database '{database}'...")
        schema = _fetch_mysql_schema(
            {"host": host, "user": user, "password": password, "database": database, "port": port}
        )
        schema_text = _schema_to_text(schema)
        print(f"   ✓ Found {len(schema)} tables")

        # Step 3: Initialize LLM
        print("\n🤖 Initializing LLM...")
        if not LLM_AVAILABLE:
            return {
                "error": "LLM libraries missing. Install: pip install langchain-ollama",
                "success": False
            }

        model_name = os.environ.get("OLLAMA_MODEL", "llama3.1:8b")
        base_url = os.environ.get("http://172.17.22.12:11434", "http://172.17.22.12:11434")
        
        
        try:
            llm = OllamaLLM(model=model_name, base_url=base_url, temperature=0.1)
            print(f"   ✓ Using model: {model_name}")
        except Exception as e:
            print(f"   ❌ Failed to initialize LLM: {e}")

        # Step 4: Generate SQL with Agentic Retry
        sql = None
        df = None
        execution_errors = []
        
        if use_agentic:
            agentic_engine = AgenticSQLEngine(llm, schema_text)
            sql, sql_stats = agentic_engine.generate_sql_with_retry(
                user_query, max_retries, mysql_config
            )
            execution_errors = sql_stats.get('errors', 0)
            attempts = sql_stats.get('attempts', 1)
        else:
            # Fallback to simple generation
            sql = _extract_sql(llm.invoke(f"Generate SQL for: {user_query}\nSchema:\n{schema_text}"))
            attempts = 1
            execution_errors = 0
        
        if sql is None:
            return {
                "error": "Failed to generate SQL after all retries",
                "attempts": attempts,
                "success": False,
                "query_complexity": complexity
            }

        print(f"\n✅ COMPLETE SQL Generated:\n{sql}\n")

        # Step 5: Execute SQL
        try:
            conn = mysql.connector.connect(**mysql_config)
            df = pd.read_sql(sql, conn)
            conn.close()
            print(f"   ✅ Retrieved {len(df)} rows × {len(df.columns)} columns")
        except Exception as e:
            return {
                "error": f"SQL execution failed: {str(e)}",
                "sql_query": sql,
                "success": False
            }

        # Step 6: Analyze data
        print(f"\n📊 Analyzing data structure...")
        analysis = _analyze_dataframe(df)
        
        # Step 7: Generate visualizations - CRITICAL
        print(f"\n🎨 Starting visualization generation...")
        visualizations = _generate_visualizations(df, analysis, user_query)
        
        if not visualizations or len(visualizations.get('chart_order', [])) == 0:
            print("   ⚠️  WARNING: No visualizations generated!")
            print("   Attempting emergency fallback visualization...")
            # Emergency fallback - create at least one chart
            if len(df.columns) >= 2:
                try:
                    cat_col = df.columns[0]
                    num_col = df.columns[-1]
                    if pd.api.types.is_numeric_dtype(df[num_col]):
                        img = _create_bar_chart(df, cat_col, num_col, "Data Overview")
                        if img:
                            visualizations = {
                                "bar": {
                                    "type": "bar",
                                    "image": img,
                                    "base64": img,
                                    "description": "Data overview",
                                    "title": "Data Overview"
                                },
                                "primary": "bar",
                                "chart_order": ["bar"]
                            }
                            print("   ✅ Emergency visualization created")
                except Exception as e:
                    print(f"   ❌ Emergency visualization failed: {e}")
        else:
            print(f"   ✅ Generated {len([k for k in visualizations.keys() if k not in ['primary', 'chart_order']])} charts")

        # Step 8: Generate insights
        print("\n💡 Generating professional insights...")
        narrative = _build_rich_narrative(llm, schema_text, user_query, sql, df)
        
        processing_time = round(time.time() - start_time, 2)
        
        # Build result
        result = {
            "success": True,
            "title": user_query,
            "sql_query": sql,
            "sql": sql,
            "query": sql,
            "data": df.to_dict(orient="records") if not df.empty else [],
            "rows": df.to_dict(orient="records") if not df.empty else [],
            "columns": df.columns.tolist() if not df.empty else [],
            "summary": narrative.get("summary", []),
            "insights": narrative.get("insights", []),
            "strategy": narrative.get("strategy", []),
            "recommendations": narrative.get("strategy", []),
            "visualizations": visualizations,
            "charts": visualizations,
            "chart_types_generated": [k for k in visualizations.keys() if k not in ['primary', 'chart_order']],
            "data_analysis": {
                "row_count": analysis["row_count"],
                "column_count": analysis["col_count"],
                "numeric_columns": analysis["numeric_cols"],
                "categorical_columns": analysis["categorical_cols"],
                "datetime_columns": analysis["datetime_cols"],
                "has_geospatial": bool(analysis["geo_cols"]["lat"] and analysis["geo_cols"]["lon"]),
                "recommended_charts": analysis["recommended_charts"]
            },
            "agent_stats": {
                "attempts": attempts,
                "errors": execution_errors,
                "execution_errors": [] if execution_errors == 0 else [f"{execution_errors} errors occurred"],
                "processing_time_seconds": processing_time,
                "processing_time": processing_time,
                "query_complexity": complexity,
                "complexity": complexity,
                "max_retries": max_retries,
                "agent_type": "agentic-ai-ollama" if use_agentic else "simple-ollama",
                "visualizations_created": len([k for k in visualizations.keys() if k not in ['primary', 'chart_order']]),
                "charts_created": len([k for k in visualizations.keys() if k not in ['primary', 'chart_order']]),
                "model": model_name
            }
        }
        
        # Step 9: Store in ChromaDB if available
        if chroma_store and chroma_store.enabled:
            print("\n💾 Storing results in ChromaDB...")
            result_id = chroma_store.store_sql_result(
                user_query, sql, df, narrative, visualizations, result['agent_stats']
            )
            result['chroma_id'] = result_id
        
        # Step 10: Generate PDF if requested
        pdf_path = None
        if generate_pdf:
            if not pdf_output:
                pdf_output = f"analytics_report_{int(time.time())}.pdf"
            
            pdf_success = _generate_pdf_report(
                pdf_output, user_query, sql, df, narrative, visualizations
            )
            if pdf_success:
                pdf_path = pdf_output
                result["pdf_report"] = pdf_path
        
        print("\n" + "="*60)
        print(f"✅ ANALYTICS COMPLETE ({processing_time}s)")
        print("="*60 + "\n")

        return result

    except Exception as e:
        print(f"\n❌ CRITICAL ERROR: {e}")
        traceback.print_exc()
        return {
            "error": str(e),
            "trace": traceback.format_exc(),
            "success": False
        }

# ============= HTML REPORT GENERATION =============
def generate_html_report(result: Dict[str, Any], output_file: str = "analytics_report.html") -> str:
    """Generate a beautiful HTML report from analytics results.
    
    Args:
        result: Output from run_langgraph_analytics()
        output_file: Path to save HTML report
        
    Returns:
        Path to generated HTML file
    """
    if not result.get("success"):
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Analytics Report - Error</title>
            <style>
                body {{ font-family: Arial, sans-serif; padding: 40px; background: #f5f5f5; }}
                .error {{ background: #fee; border: 2px solid #c33; padding: 20px; border-radius: 8px; }}
            </style>
        </head>
        <body>
            <div class="error">
                <h1>❌ Analytics Error</h1>
                <p><strong>Error:</strong> {result.get('error', 'Unknown error')}</p>
            </div>
        </body>
        </html>
        """
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html)
        return output_file
    
    # Build HTML report
    visualizations = result.get("visualizations", {})
    
    charts_html = ""
    chart_order = visualizations.get("chart_order", [])
    for chart_type in chart_order:
        if chart_type in visualizations:
            chart_data = visualizations[chart_type]
            if "image" in chart_data or "base64" in chart_data:
                title = chart_data.get("title", chart_type.title())
                desc = chart_data.get("description", "")
                img_b64 = chart_data.get("base64") or chart_data.get("image")
                
                charts_html += f"""
                <div class="chart-container">
                    <h3>{title}</h3>
                    <p class="chart-desc">{desc}</p>
                    <img src="data:image/png;base64,{img_b64}" alt="{title}" />
                </div>
                """
    
    summary_html = "".join([f"<li>{s}</li>" for s in result.get("summary", [])])
    insights_html = "".join([f"<li>{i}</li>" for s in result.get("insights", [])])
    strategy_html = "".join([f"<li>{s}</li>" for s in result.get("strategy", [])])
    
    # Data table
    data_html = ""
    if result.get("data"):
        columns = result.get("columns", [])
        data_html = "<table class='data-table'><thead><tr>"
        data_html += "".join([f"<th>{col}</th>" for col in columns])
        data_html += "</tr></thead><tbody>"
        
        for row in result["data"][:50]:
            data_html += "<tr>"
            data_html += "".join([f"<td>{row.get(col, '')}</td>" for col in columns])
            data_html += "</tr>"
        
        data_html += "</tbody></table>"
        
        if len(result["data"]) > 50:
            data_html += f"<p class='note'>Showing first 50 of {len(result['data'])} rows</p>"
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Agentic AI Analytics Report - {result.get('title', 'Query Results')}</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 40px 20px;
                color: #333;
            }}
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                background: white;
                border-radius: 16px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                overflow: hidden;
            }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 40px;
                text-align: center;
            }}
            .header h1 {{
                font-size: 2.5em;
                margin-bottom: 10px;
                font-weight: 700;
            }}
            .header .subtitle {{
                font-size: 1.1em;
                opacity: 0.9;
            }}
            .content {{
                padding: 40px;
            }}
            .section {{
                margin-bottom: 40px;
            }}
            .section h2 {{
                font-size: 1.8em;
                color: #667eea;
                margin-bottom: 20px;
                border-bottom: 3px solid #667eea;
                padding-bottom: 10px;
            }}
            .sql-box {{
                background: #f8f9fa;
                border-left: 4px solid #667eea;
                padding: 20px;
                border-radius: 8px;
                overflow-x: auto;
                font-family: 'Courier New', monospace;
                font-size: 0.95em;
                line-height: 1.6;
            }}
            .chart-container {{
                margin: 30px 0;
                padding: 20px;
                background: #f8f9fa;
                border-radius: 12px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            }}
            .chart-container h3 {{
                color: #667eea;
                margin-bottom: 10px;
                font-size: 1.4em;
            }}
            .chart-desc {{
                color: #666;
                margin-bottom: 15px;
                font-style: italic;
            }}
            .chart-container img {{
                width: 100%;
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            }}
            ul {{
                list-style: none;
                padding: 0;
            }}
            ul li {{
                padding: 12px 20px;
                margin: 10px 0;
                background: #f8f9fa;
                border-left: 4px solid #667eea;
                border-radius: 4px;
                line-height: 1.6;
            }}
            .data-table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
                font-size: 0.9em;
            }}
            .data-table th {{
                background: #667eea;
                color: white;
                padding: 12px;
                text-align: left;
                font-weight: 600;
            }}
            .data-table td {{
                padding: 10px 12px;
                border-bottom: 1px solid #e0e0e0;
            }}
            .data-table tr:hover {{
                background: #f5f5f5;
            }}
            .stats {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin: 20px 0;
            }}
            .stat-box {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 20px;
                border-radius: 12px;
                text-align: center;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            }}
            .stat-box .number {{
                font-size: 2.5em;
                font-weight: bold;
                margin-bottom: 5px;
            }}
            .stat-box .label {{
                font-size: 0.9em;
                opacity: 0.9;
            }}
            .note {{
                color: #666;
                font-style: italic;
                margin-top: 10px;
            }}
            .footer {{
                text-align: center;
                padding: 20px;
                background: #f8f9fa;
                color: #666;
                font-size: 0.9em;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🤖 Agentic AI Analytics Report</h1>
                <p class="subtitle">{result.get('title', 'Data Analysis')}</p>
            </div>
            
            <div class="content">
                <div class="section">
                    <h2>📈 Key Metrics</h2>
                    <div class="stats">
                        <div class="stat-box">
                            <div class="number">{result.get('data_analysis', {}).get('row_count', 0)}</div>
                            <div class="label">Rows Retrieved</div>
                        </div>
                        <div class="stat-box">
                            <div class="number">{result.get('data_analysis', {}).get('column_count', 0)}</div>
                            <div class="label">Columns</div>
                        </div>
                        <div class="stat-box">
                            <div class="number">{len([k for k in visualizations.keys() if k not in ['primary', 'chart_order']])}</div>
                            <div class="label">Visualizations</div>
                        </div>
                        <div class="stat-box">
                            <div class="number">{result.get('agent_stats', {}).get('processing_time_seconds', 0)}s</div>
                            <div class="label">Processing Time</div>
                        </div>
                    </div>
                </div>
                
                <div class="section">
                    <h2>🔍 SQL Query</h2>
                    <div class="sql-box">{result.get('sql_query', 'N/A')}</div>
                </div>
                
                <div class="section">
                    <h2>📊 Visualizations</h2>
                    {charts_html if charts_html else '<p class="note">No visualizations generated</p>'}
                </div>
                
                <div class="section">
                    <h2>📋 Summary</h2>
                    <ul>{summary_html if summary_html else '<li>No summary available</li>'}</ul>
                </div>
                
                <div class="section">
                    <h2>💡 Key Insights</h2>
                    <ul>{insights_html if insights_html else '<li>No insights available</li>'}</ul>
                </div>
                
                <div class="section">
                    <h2>🎯 Recommended Actions</h2>
                    <ul>{strategy_html if strategy_html else '<li>No recommendations available</li>'}</ul>
                </div>
                
                <div class="section">
                    <h2>📄 Data Preview</h2>
                    {data_html if data_html else '<p class="note">No data to display</p>'}
                </div>
            </div>
            
            <div class="footer">
                Generated by Agentic AI Analytics • Model: {result.get('agent_stats', {}).get('model', 'N/A')} • 
                Complexity: {result.get('agent_stats', {}).get('query_complexity', 'N/A')} •
                Attempts: {result.get('agent_stats', {}).get('attempts', 1)}
            </div>
        </div>
    </body>
    </html>
    """
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print(f"\n📄 HTML report saved to: {output_file}")
    return output_file


# ============= FLASK API ENDPOINTS =============

@app.route('/api/health', methods=['GET'])
def health_check():
    """System health check"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'mode': 'agentic_ai_with_chromadb',
        'features': {
            'agentic_sql_generation': True,
            'self_correcting_ai': True,
            'chromadb_result_storage': CHROMADB_AVAILABLE,
            'professional_analytics': True,
            'visualization_generation': True,
            'pdf_generation': PDF_AVAILABLE,
            'llm_available': LLM_AVAILABLE
        }
    })


@app.route('/api/schema', methods=['POST'])
def get_schema():
    """Get database schema"""
    data = request.json
    mysql_config = data.get('mysql_config')
    
    if not mysql_config:
        return jsonify({'error': 'mysql_config required'}), 400
    
    try:
        schema = _fetch_mysql_schema(mysql_config)
        schema_text = _schema_to_text(schema)
        
        return jsonify({
            'tables': list(schema.keys()),
            'schema': {
                table: {
                    'columns': info['columns'],
                    'row_count': info['row_count']
                }
                for table, info in schema.items()
            },
            'schema_text': schema_text
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/generate-insight', methods=['POST'])
def generate_insight():
    """Generate insights from user query using Agentic AI"""
    data = request.json
    user_query = data.get('query', '')
    mysql_config = data.get('mysql_config')
    use_agentic = data.get('use_agentic', True)
    
    if not user_query:
        return jsonify({'error': 'Query required'}), 400
    
    if not mysql_config:
        return jsonify({'error': 'mysql_config required'}), 400
    
    # Initialize ChromaDB if available
    chroma_store = None
    if CHROMADB_AVAILABLE:
        chroma_store = ChromaDBResultStore()
    
    result = run_langgraph_analytics(
        mysql_config, 
        user_query, 
        generate_pdf=False,
        use_agentic=use_agentic,
        chroma_store=chroma_store
    )
    
    if result is None or not result.get('success'):
        return jsonify({'error': result.get('error', 'Failed to generate insight')}), 500
    
    return jsonify(result)


@app.route('/api/stored-results', methods=['GET'])
def get_stored_results():
    """Get all stored query results from ChromaDB"""
    if not CHROMADB_AVAILABLE:
        return jsonify({'error': 'ChromaDB not available'}), 500
    
    chroma_store = ChromaDBResultStore()
    if not chroma_store.enabled:
        return jsonify({'error': 'ChromaDB not initialized'}), 500
    
    limit = request.args.get('limit', 50, type=int)
    results = chroma_store.get_all_stored_queries(limit)
    
    return jsonify({
        'results': results,
        'count': len(results)
    })


@app.route('/api/result/<result_id>', methods=['GET'])
def get_result_by_id(result_id):
    """Get specific stored result from ChromaDB"""
    if not CHROMADB_AVAILABLE:
        return jsonify({'error': 'ChromaDB not available'}), 500
    
    chroma_store = ChromaDBResultStore()
    if not chroma_store.enabled:
        return jsonify({'error': 'ChromaDB not initialized'}), 500
    
    result = chroma_store.get_stored_result(result_id)
    
    if result is None:
        return jsonify({'error': 'Result not found'}), 404
    
    return jsonify(result)


@app.route('/api/search-similar', methods=['POST'])
def search_similar():
    """Search for similar past queries in ChromaDB"""
    if not CHROMADB_AVAILABLE:
        return jsonify({'error': 'ChromaDB not available'}), 500
    
    data = request.json
    query = data.get('query', '')
    n_results = data.get('n_results', 5)
    
    if not query:
        return jsonify({'error': 'Query required'}), 400
    
    chroma_store = ChromaDBResultStore()
    if not chroma_store.enabled:
        return jsonify({'error': 'ChromaDB not initialized'}), 500
    
    similar = chroma_store.search_similar_results(query, n_results)
    
    return jsonify({
        'query': query,
        'similar_results': similar,
        'count': len(similar)
    })


@app.route('/api/download-report', methods=['POST'])
def download_report():
    """Generate and download PDF report"""
    if not PDF_AVAILABLE:
        return jsonify({'error': 'PDF generation not available - install reportlab'}), 500
    
    try:
        data = request.json
        
        if 'insight' not in data:
            return jsonify({'error': 'Insight data required'}), 400
        
        insight_data = data['insight']
        visualizations = insight_data.get('visualizations', {})
        
        # Generate PDF in memory
        output_path = f"temp_report_{int(time.time())}.pdf"
        success = _generate_pdf_report(
            output_path,
            insight_data.get('title', 'Query'),
            insight_data.get('sql_query', ''),
            pd.DataFrame(insight_data.get('data', [])),
            {
                'summary': insight_data.get('summary', []),
                'insights': insight_data.get('insights', []),
                'strategy': insight_data.get('strategy', [])
            },
            visualizations
        )
        
        if not success:
            return jsonify({'error': 'PDF generation failed'}), 500
        
        return send_file(
            output_path,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"AgenticAI_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/chromadb-stats', methods=['GET'])
def chromadb_stats():
    """Get ChromaDB statistics"""
    if not CHROMADB_AVAILABLE:
        return jsonify({'error': 'ChromaDB not available'}), 500
    
    chroma_store = ChromaDBResultStore()
    if not chroma_store.enabled:
        return jsonify({'error': 'ChromaDB not initialized'}), 500
    
    try:
        result_count = chroma_store.results_collection.count()
        
        return jsonify({
            'chromadb': {
                'stored_results': result_count,
                'embedding_model': EMBEDDING_MODEL,
                'persist_directory': CHROMA_PERSIST_DIR
            },
            'purpose': 'SQL result storage for report generation and analytics'
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/example-queries', methods=['GET'])
def get_example_queries():
    """Get example queries"""
    examples = [
        "Show me the top 10 products by revenue",
        "What are the top 5 customers by total sales?",
        "Compare revenue across different years",
        "Show me revenue breakdown by product category",
        "Which products have highest sales volume?",
        "What's the average order quantity by category?",
        "Show me top selling products in each category",
        "List all products with revenue above 100000"
    ]
    return jsonify({'examples': examples})


# ============= MAIN EXECUTION =============
if __name__ == "__main__":
    # Example usage
    config = {
        "host": "localhost",
        "user": "root",
        "password": "your_password",
        "database": "your_database",
        "port": 3306
    }
    
    query = "Show me the top 10 products by sales revenue"
    
    # Initialize ChromaDB if available
    chroma_store = None
    if CHROMADB_AVAILABLE:
        chroma_store = ChromaDBResultStore()
    
    # Run analytics with both HTML and PDF reports
    result = run_langgraph_analytics(
        config, 
        query, 
        generate_pdf=True,
        use_agentic=True,
        chroma_store=chroma_store
    )
    
    if result.get("success"):
        # Generate HTML report
        generate_html_report(result, f"report_{int(time.time())}.html")
        
        print(f"\n✅ SUCCESS!")
        print(f"   SQL: {result['sql_query'][:100]}...")
        print(f"   Rows: {result['data_analysis']['row_count']}")
        print(f"   Charts: {', '.join(result['chart_types_generated'])}")
        print(f"   Time: {result['agent_stats']['processing_time_seconds']}s")
        print(f"   Attempts: {result['agent_stats']['attempts']}")
        
        if result.get('chroma_id'):
            print(f"   ChromaDB ID: {result['chroma_id'][:12]}...")
    else:
        print(f"\n❌ FAILED: {result.get('error')}")
    
    # Start Flask API
    print("\n" + "="*80)
    print("🌐 AGENTIC AI ANALYTICS API SERVER")
    print("="*80)
    print(f"\n✨ System Architecture:")
    print(f"  🤖 Agentic AI Decision Engine")
    print(f"     • Self-correcting SQL generation")
    print(f"     • Intelligent error analysis & auto-fix")
    print(f"     • Adaptive retry strategies")
    print(f"  🔵 ChromaDB Integration: {'✅ Enabled' if CHROMADB_AVAILABLE else '❌ Not Available'}")
    print(f"     • Store SQL query results")
    print(f"     • Store professional insights")
    print(f"     • Enable report generation & analytics")
    print(f"     • Search similar past queries")
    print(f"  📊 Professional Analysis")
    print(f"     • Data-driven insights")
    print(f"     • Strategic recommendations")
    print(f"     • Multi-format visualizations")
    print(f"  📄 Report Generation: {'✅ Enabled' if PDF_AVAILABLE else '❌ PDF Not Available'}")
    print(f"     • PDF reports with visualizations")
    print(f"     • HTML reports with interactive design")
    print(f"     • Leverages ChromaDB stored insights")
    print("\n" + "="*80 + "\n")
    
    print("📋 API Endpoints:")
    print("  • POST /api/generate-insight - Generate insights (Agentic AI)")
    print("  • GET /api/stored-results - Get all stored results")
    print("  • GET /api/result/<id> - Get specific result")
    print("  • POST /api/search-similar - Find similar queries")
    print("  • POST /api/download-report - Generate PDF report")
    print("  • GET /api/chromadb-stats - ChromaDB statistics")
    print("  • POST /api/schema - Get database schema")
    print("  • GET /api/health - System health")

    print("  • GET /api/example-queries - Example queries")
    print("\n" + "="*80 + "\n")
    
    # Uncomment to start Flask server
    # app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)
    """Create a histogram for numeric distribution."""
  

def _create_histogram(df: pd.DataFrame, value_col: str, title: str = None) -> Optional[str]:
    """Create a histogram for numeric distribution."""
    try:
        plt.close("all")
        fig, ax = plt.subplots(figsize=(12, 7))
        
        data = df[value_col].dropna()
        
        if len(data) == 0:
            return None
        
        n, bins, patches = ax.hist(
            data,
            bins=30,
            color='#6366f1',
            alpha=0.7,
            edgecolor='black',
            linewidth=1.2
        )
        
        for i, patch in enumerate(patches):
            patch.set_facecolor(plt.cm.viridis(i / len(patches)))
        
        mean_val = data.mean()
        median_val = data.median()
        ax.axvline(mean_val, color='red', linestyle='--', linewidth=2, label=f'Mean: {mean_val:.2f}')
        ax.axvline(median_val, color='green', linestyle='--', linewidth=2, label=f'Median: {median_val:.2f}')
        
        ax.set_xlabel(value_col, fontsize=12, fontweight='bold')
        ax.set_ylabel('Frequency', fontsize=12, fontweight='bold')
        ax.set_title(title or f"Distribution of {value_col}", fontsize=14, fontweight='bold', pad=20)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        ax.legend()
        
        plt.tight_layout()
        return _fig_to_base64(fig)
    except Exception as e:
        print(f"   ❌ Histogram error: {e}")
        traceback.print_exc()
        return None


def _create_scatter_plot(df: pd.DataFrame, x_col: str, y_col: str, title: str = None) -> Optional[str]:
    """Create a scatter plot for relationship analysis."""
    try:
        plt.close("all")
        fig, ax = plt.subplots(figsize=(12, 7))
        
        plot_df = df[[x_col, y_col]].dropna()
        if len(plot_df) > 1000:
            plot_df = plot_df.sample(1000)
        
        scatter = ax.scatter(plot_df[x_col], plot_df[y_col], 
                            alpha=0.6, s=60, c=plot_df[y_col],
                            cmap='viridis', edgecolors='black', linewidth=0.5)
        
        if len(plot_df) > 5:
            try:
                z = np.polyfit(plot_df[x_col], plot_df[y_col], 1)
                p = np.poly1d(z)
                ax.plot(plot_df[x_col].sort_values(), p(plot_df[x_col].sort_values()), 
                       "r--", linewidth=2.5, alpha=0.8, label='Trend Line')
                
                corr = plot_df[x_col].corr(plot_df[y_col])
                ax.text(0.05, 0.95, f'Correlation: {corr:.3f}', 
                       transform=ax.transAxes, fontsize=11, 
                       verticalalignment='top',
                       bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
                ax.legend()
            except Exception:
                pass
        
        plt.colorbar(scatter, ax=ax, label=y_col)
        ax.set_xlabel(x_col, fontsize=12, fontweight='bold')
        ax.set_ylabel(y_col, fontsize=12, fontweight='bold')
        ax.set_title(title or f"{y_col} vs {x_col}", fontsize=14, fontweight='bold', pad=20)
        ax.grid(True, alpha=0.3, linestyle='--')
        
        plt.tight_layout()
        return _fig_to_base64(fig)
    except Exception as e:
        print(f"   ❌ Scatter plot error: {e}")
        traceback.print_exc()
        return None


def _create_geospatial_map(df: pd.DataFrame, lat_col: str, lon_col: str, title: str = None) -> Optional[str]:
    """Create a geospatial scatter map."""
    try:
        plt.close("all")
        fig, ax = plt.subplots(figsize=(14, 9))
        
        plot_df = df[[lat_col, lon_col]].dropna()
        if len(plot_df) > 2000:
            plot_df = plot_df.sample(2000)
        
        scatter = ax.scatter(plot_df[lon_col], plot_df[lat_col],
                            alpha=0.6, s=40, c='#0ea5e9',
                            edgecolors='#075985', linewidth=0.8)
        
        ax.set_xlabel('Longitude', fontsize=12, fontweight='bold')
        ax.set_ylabel('Latitude', fontsize=12, fontweight='bold')
        ax.set_title(title or f"Geospatial Distribution ({len(plot_df)} points)", 
                    fontsize=14, fontweight='bold', pad=20)
        ax.grid(True, alpha=0.3, linestyle='--')
        
        ax.text(0.02, 0.98, f'Total Points: {len(plot_df)}', 
               transform=ax.transAxes, fontsize=10, 
               verticalalignment='top',
               bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))
        
        plt.tight_layout()
        return _fig_to_base64(fig)
    except Exception as e:
        print(f"   ❌ Geospatial chart error: {e}")
        traceback.print_exc()
        return None


def _generate_visualizations(df: pd.DataFrame, analysis: Dict[str, Any], 
                            user_query: str = "") -> Dict[str, Any]:
    """FIXED: Generate visualizations with AGGRESSIVE fallbacks and multiple chart types."""
    visualizations = {}
    
    if df.empty:
        print("   ⚠️  DataFrame is empty")
        return visualizations
    
    datetime_cols = analysis["datetime_cols"]
    numeric_cols = analysis["numeric_cols"]
    categorical_cols = analysis["categorical_cols"]
    geo_cols = analysis["geo_cols"]
    
    query_lower = user_query.lower()
    chart_candidates = []
    
    print(f"\n🎨 GENERATING VISUALIZATIONS...")
    print(f"   Query: {user_query}")
    print(f"   Shape: {df.shape}")
    print(f"   Numeric: {numeric_cols}")
    print(f"   Categorical: {categorical_cols}")
    
    # CRITICAL FIX: Ensure we have at least one categorical and one numeric
    if not categorical_cols and len(df.columns) >= 1:
        print(f"   ⚠️  No categorical columns. Forcing detection...")
        for col in df.columns:
            if not pd.api.types.is_numeric_dtype(df[col]):
                categorical_cols = [col]
                print(f"   ✓ Forced categorical: {col}")
                break
        if not categorical_cols:
            categorical_cols = [df.columns[0]]
            print(f"   ✓ Using first column as categorical: {df.columns[0]}")
    
    if not numeric_cols and len(df.columns) >= 2:
        print(f"   ⚠️  No numeric columns. Forcing detection...")
        for col in df.columns:
            if pd.api.types.is_numeric_dtype(df[col]):
                numeric_cols = [col]
                print(f"   ✓ Forced numeric: {col}")
                break
    
    def add_chart_candidate(key: str, img: Optional[str], title: str, description: str, priority: float):
        if not img:
            return
        chart_candidates.append({
            "key": key,
            "data": {
                "type": key,
                "image": img,
                "base64": img,
                "description": description,
                "title": title
            },
            "priority": priority
        })
        print(f"      ✅ Added chart candidate '{key}' (priority {priority})")
    
    def keyword_bonus(*keywords):
        return 10 if any(kw in query_lower for kw in keywords) else 0
    
    # GEOSPATIAL (high priority when lat/lon exist or user asks for map/regions)
    print("\n   ➜ Checking for geospatial data")
    if geo_cols["lat"] and geo_cols["lon"]:
        base_priority = 85 + keyword_bonus("map", "region", "geo", "location", "lat", "lon")
        print(f"      Creating geospatial map with priority {base_priority}")
        img = _create_geospatial_map(df, geo_cols["lat"], geo_cols["lon"], title="Geographic Distribution")
        add_chart_candidate("geospatial", img, "Geospatial Map", "Geographic distribution of records", base_priority)
    
    # BAR CHART (comparison / top analysis)
    print("\n   ➜ Evaluating bar/column chart")
    if categorical_cols:
        cat_col = categorical_cols[0]
        if numeric_cols:
            num_col = numeric_cols[-1]
            priority = 65 + keyword_bonus("top", "compare", "comparison", "vs", "by", "highest")
            img = _create_bar_chart(df, cat_col, num_col, title=f"{num_col} by {cat_col}")
            add_chart_candidate("bar", img, f"Bar Chart: {cat_col}", f"{num_col} comparison by {cat_col}", priority)
        else:
            priority = 50 + keyword_bonus("count", "frequency")
            img = _create_bar_chart_count(df, cat_col, title=f"Count by {cat_col}")
            add_chart_candidate("bar_count", img, f"Bar Chart: {cat_col}", f"Count distribution for {cat_col}", priority)
    
    # PIE CHART (distribution insights)
    print("\n   ➜ Evaluating pie chart")
    if categorical_cols:
        cat_col = categorical_cols[0]
        pie_keywords = keyword_bonus("share", "distribution", "ratio", "percentage", "pie")
        if numeric_cols:
            num_col = numeric_cols[-1]
            img = _create_pie_chart(df, cat_col, num_col, title=f"{num_col} Distribution")
        else:
            img = _create_pie_chart_count(df, cat_col, title=f"{cat_col} Distribution")
        add_chart_candidate("pie", img, f"Pie Chart: {cat_col}", f"Distribution by {cat_col}", 45 + pie_keywords)
    
    # HISTOGRAM (numeric distribution)
    print("\n   ➜ Evaluating histogram")
    if numeric_cols:
        num_col = numeric_cols[-1]
        priority = 40 + keyword_bonus("distribution", "spread", "variance", "histogram")
        img = _create_histogram(df, num_col, title=f"Distribution of {num_col}")
        add_chart_candidate("histogram", img, f"Histogram: {num_col}", f"Distribution of {num_col}", priority)
    
    # LINE CHART (time trends)
    print("\n   ➜ Evaluating line chart")
    if datetime_cols and numeric_cols:
        time_col = datetime_cols[0]
        num_col = numeric_cols[-1]
        priority = 70 + keyword_bonus("trend", "over time", "timeline", "growth", "daily", "monthly")
        img = _create_line_chart(df, time_col, num_col, title=f"{num_col} Over Time")
        add_chart_candidate("line", img, "Line Chart: Trend Analysis", f"{num_col} trend over {time_col}", priority)
    
    # SCATTER PLOT (relationship)
    print("\n   ➜ Evaluating scatter plot")
    if len(numeric_cols) >= 2:
        x_col, y_col = numeric_cols[0], numeric_cols[1]
        priority = 55 + keyword_bonus("correlation", "relationship", "impact", "vs")
        img = _create_scatter_plot(df, x_col, y_col, title=f"{y_col} vs {x_col}")
        add_chart_candidate("scatter", img, f"Scatter Plot: {y_col} vs {x_col}",
                            f"Relationship between {x_col} and {y_col}", priority)
    
    # Limit to top 2 charts
    if chart_candidates:
        chart_candidates.sort(key=lambda c: c["priority"], reverse=True)
        selected = chart_candidates[:2]
        chart_order = []
        for candidate in selected:
            key = candidate["key"]
            visualizations[key] = candidate["data"]
            chart_order.append(key)
        visualizations["chart_order"] = chart_order
        visualizations["primary"] = chart_order[0]
    else:
        print("   ⚠️ No charts created. Attempting fallback bar chart.")
        if len(df.columns) >= 2:
            fallback_cat = categorical_cols[0] if categorical_cols else df.columns[0]
            fallback_num = numeric_cols[0] if numeric_cols else None
            img = None
            if fallback_num:
                img = _create_bar_chart(df, fallback_cat, fallback_num, title="Data Overview")
            if img:
                visualizations["bar"] = {
                    "type": "bar",
                    "image": img,
                    "base64": img,
                    "description": "Data overview",
                    "title": "Data Overview"
                }
                visualizations["chart_order"] = ["bar"]
                visualizations["primary"] = "bar"
    
    print(f"\n✅ VISUALIZATION SUMMARY:")
    print(f"   Candidates generated: {len(chart_candidates)}")
    print(f"   Selected charts: {visualizations.get('chart_order', [])}")
    print(f"   Primary chart: {visualizations.get('primary', 'none')}\n")
    
    return visualizations