# -*- coding: utf-8 -*-
import io, re
src = io.open('app.py', encoding='utf-8').read()
# tabs 定义
m = re.search(r'st\.tabs\(\[(.*?)\]\)', src, re.S)
print('TABS:', m.group(1)[:600] if m else 'N/A')
# sidebar radio 选项
m2 = re.search(r'battery_type = st\.radio\((.*?)\)', src, re.S)
print('SIDEBAR RADIO:', m2.group(1)[:400] if m2 else 'N/A')
# tab 标题
for t in re.findall(r'st\.(?:title|header|subheader|markdown)\(([\'"][^\'"]{4,80}[\'"])\)', src)[:40]:
    print('HDR:', t)
