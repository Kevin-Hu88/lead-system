# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, ".")
from dashboard.app import app
from crm.models import db, Lead

with app.app_context():
    # Check classified/forum/search leads
    for src in ["58同城", "分类信息", "问答平台", "百度贴吧", "知乎", "search"]:
        leads = Lead.query.filter_by(source=src).all()
        if leads:
            s = len([l for l in leads if l.lead_level == "S"])
            a = len([l for l in leads if l.lead_level == "A"])
            b = len([l for l in leads if l.lead_level == "B"])
            with_phone = len([l for l in leads if l.phone])
            print("%-10s total=%-4d S=%-3d A=%-3d B=%-3d phone=%d" % (
                src, len(leads), s, a, b, with_phone
            ))
            # Show sample
            for l in leads[:2]:
                print("  [%s] %s | %s" % (l.lead_level, l.name[:40], l.phone or "(无)"))
