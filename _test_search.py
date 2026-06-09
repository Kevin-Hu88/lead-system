# -*- coding: utf-8 -*-
"""Test improved search harvester v2"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, ".")

from dashboard.app import app
from crm.models import db, Lead
from lead_harvester.search_harvester import SearchHarvester

with app.app_context():
    h = SearchHarvester()
    
    # Test a few queries
    test_queries = [
        ("武汉 车棚 安装 电话", "物业", "找车棚安装服务", "high"),
        ("武汉 充电桩 车棚 配套", "新能源", "充电桩配套车棚", "high"),
    ]
    
    total_found = 0
    total_saved = 0
    for query, ctype, desc, priority in test_queries:
        leads_bing = h._search_bing(query)
        leads_baidu = h._search_baidu(query)
        all_leads = leads_bing + leads_baidu
        all_leads = h._deduplicate(all_leads)
        
        # Add metadata
        for lead in all_leads:
            lead["customer_type"] = ctype
            lead["demand_desc"] = f"[{priority}] {desc} | {lead.get('demand_desc', '')}"
            lead["area"] = h._extract_area(lead.get("name", "") + " " + lead.get("demand_desc", ""))
        
        saved = h._save_leads(all_leads)
        total_found += len(all_leads)
        total_saved += saved
        
        print("[%s] found=%d saved=%d" % (query[:20], len(all_leads), saved))
        for l in all_leads[:2]:
            print("  -> %s | %s" % (l["name"][:35], l["phone"] or "(无)"))
    
    print("\nTotal: found=%d saved=%d" % (total_found, total_saved))
    
    # Check search leads
    print("\n=== Search leads ===")
    leads = Lead.query.filter_by(source="search").order_by(Lead.total_score.desc()).limit(10).all()
    for l in leads:
        print("[%s] %s | %s | score=%d" % (l.lead_level, l.name[:35], l.phone or "(无)", l.total_score))
