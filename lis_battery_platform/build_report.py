"""
生成锂硫电池交互式HTML报告
"""
import sys, os, json
import numpy as np
import pandas as pd

sys.path.insert(0, '/share/bf/lis_battery_platform')
from generate_data import generate_all_data, LIQUID_FILLERS, SOLID_FILLERS
from modeling import (train_models, get_feature_importance_summary,
                      LIQUID_FEATURES, LIQUID_TARGETS,
                      SOLID_FEATURES, SOLID_TARGETS)

print("[1/4] 生成数据...")
liquid_df, solid_df = generate_all_data()
print(f"  液态: {len(liquid_df)} 条, 固态: {len(solid_df)} 条")

print("[2/4] 训练模型...")
liquid_results, liquid_le, liquid_scaler = train_models(
    liquid_df, LIQUID_FEATURES, LIQUID_TARGETS)
solid_results, solid_le, solid_scaler = train_models(
    solid_df, SOLID_FEATURES, SOLID_TARGETS)

print("[3/4] 序列化结果...")

def serialize_results(results, feature_cols, target_cols, df):
    """将模型结果序列化为JSON兼容字典"""
    data = {'metrics': {}, 'feature_importances': {}, 'predictions': {}, 'best_models': {}}
    
    for target in target_cols:
        if target not in results:
            continue
        tr = results[target]
        best_name = tr['best_model']
        data['best_models'][target] = best_name
        
        # 模型性能指标
        data['metrics'][target] = {}
        for mname in ['Random Forest', 'Gradient Boosting', 'Ridge Regression', 'XGBoost']:
            if mname in tr:
                data['metrics'][target][mname] = {
                    'r2': round(float(tr[mname]['r2']), 4),
                    'mae': round(float(tr[mname]['mae']), 4),
                    'rmse': round(float(tr[mname]['rmse']), 4),
                    'cv_r2_mean': round(float(tr[mname]['cv_r2_mean']), 4),
                    'cv_r2_std': round(float(tr[mname]['cv_r2_std']), 4),
                }
        
        # 特征重要性 (best model)
        data['feature_importances'][target] = {
            k: round(float(v), 5) for k, v in tr[best_name]['feature_importances'].items()
        }
        
        # 预测vs实测
        data['predictions'][target] = {
            'y_train': [round(float(x), 4) for x in tr[best_name]['y_train']],
            'y_test': [round(float(x), 4) for x in tr[best_name]['y_test']],
            'y_pred_train': [round(float(x), 4) for x in tr[best_name]['y_pred_train']],
            'y_pred_test': [round(float(x), 4) for x in tr[best_name]['y_pred_test']],
        }
    
    return data

liquid_data = serialize_results(liquid_results, LIQUID_FEATURES, LIQUID_TARGETS, liquid_df)
solid_data = serialize_results(solid_results, SOLID_FEATURES, SOLID_TARGETS, solid_df)

# 数据统计
def compute_stats(df, fillers_dict, battery_type):
    stats = {}
    # 特征列
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    stats['numeric_cols'] = numeric_cols
    stats['n_samples'] = len(df)
    
    # 各特征统计
    stats['feature_stats'] = {}
    for c in numeric_cols:
        stats['feature_stats'][c] = {
            'mean': round(float(df[c].mean()), 4),
            'std': round(float(df[c].std()), 4),
            'min': round(float(df[c].min()), 4),
            'max': round(float(df[c].max()), 4),
            'median': round(float(df[c].median()), 4),
            'hist': np.histogram(df[c], bins=30)[0].tolist(),
            'hist_edges': [round(float(x), 4) for x in np.histogram(df[c], bins=30)[1].tolist()],
        }
    
    # 相关性矩阵
    corr = df[numeric_cols].corr()
    stats['corr_matrix'] = {
        'columns': numeric_cols,
        'values': [[round(float(corr.loc[c1, c2]), 4) for c2 in numeric_cols] for c1 in numeric_cols]
    }
    
    # 材料分布
    filler_col = '填料类型'
    cat_col = '填料类别'
    filler_counts = df[filler_col].value_counts().to_dict()
    cat_counts = df[cat_col].value_counts().to_dict()
    stats['filler_counts'] = {k: int(v) for k, v in filler_counts.items()}
    stats['category_counts'] = {k: int(v) for k, v in cat_counts.items()}
    
    # 填料列表
    stats['filler_names'] = list(fillers_dict.keys())
    stats['filler_categories'] = {k: v['category'] for k, v in fillers_dict.items()}
    
    # 基底列表
    sub_col = '基底材料' if battery_type == 'liquid' else '基底/聚合物'
    stats['substrate_names'] = df[sub_col].unique().tolist()
    
    return stats

liquid_stats = compute_stats(liquid_df, LIQUID_FILLERS, 'liquid')
solid_stats = compute_stats(solid_df, SOLID_FILLERS, 'solid')

# 特征重要性汇总
liq_imp_df = get_feature_importance_summary(liquid_results, LIQUID_FEATURES)
sol_imp_df = get_feature_importance_summary(solid_results, SOLID_FEATURES)
liquid_data['importance_summary'] = {
    'features': liq_imp_df.index.tolist(),
    'values': {col: [round(float(v), 5) for v in liq_imp_df[col]] for col in liq_imp_df.columns}
}
solid_data['importance_summary'] = {
    'features': sol_imp_df.index.tolist(),
    'values': {col: [round(float(v), 5) for v in sol_imp_df[col]] for col in sol_imp_df.columns}
}

# 导出Ridge系数用于在线预测
def export_ridge_coeffs(results, target_cols, feature_cols, scaler):
    coeffs = {}
    for target in target_cols:
        if target not in results:
            continue
        tr = results[target]
        if 'Ridge Regression' in tr:
            m = tr['Ridge Regression']['model']
            coeffs[target] = {
                'coef': [round(float(c), 6) for c in m.coef_],
                'intercept': round(float(m.intercept_), 6),
                'scaler_mean': [round(float(x), 6) for x in scaler.mean_],
                'scaler_scale': [round(float(x), 6) for x in scaler.scale_],
                'use_log': target == '离子电导率(mS/cm)',
            }
    return coeffs

liquid_coeffs = export_ridge_coeffs(liquid_results, LIQUID_TARGETS, LIQUID_FEATURES, liquid_scaler)
solid_coeffs = export_ridge_coeffs(solid_results, SOLID_TARGETS, SOLID_FEATURES, solid_scaler)

# Label encoder mappings
def export_le(label_encoders):
    out = {}
    for col, le in label_encoders.items():
        out[col] = {str(c): int(i) for i, c in enumerate(le.classes_)}
    return out

liquid_le_map = export_le(liquid_le)
solid_le_map = export_le(solid_le)

# 打包所有数据
all_data = {
    'liquid': {
        'stats': liquid_stats,
        'models': liquid_data,
        'coeffs': liquid_coeffs,
        'le_map': liquid_le_map,
        'features': LIQUID_FEATURES,
        'targets': LIQUID_TARGETS,
    },
    'solid': {
        'stats': solid_stats,
        'models': solid_data,
        'coeffs': solid_coeffs,
        'le_map': solid_le_map,
        'features': SOLID_FEATURES,
        'targets': SOLID_TARGETS,
    },
}

print("[4/4] 生成HTML报告...")

html_template = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>锂硫电池材料性能预测平台</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
:root {
  --primary: #2563eb;
  --primary-light: #3b82f6;
  --accent: #10b981;
  --bg: #f8fafc;
  --card: #ffffff;
  --text: #1e293b;
  --text-light: #64748b;
  --border: #e2e8f0;
  --shadow: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -2px rgba(0,0,0,0.1);
  --radius: 12px;
}
* { margin:0; padding:0; box-sizing:border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  background: var(--bg); color: var(--text); line-height: 1.6;
}
.header {
  background: linear-gradient(135deg, #1e3a5f 0%, #2563eb 50%, #10b981 100%);
  color: white; padding: 30px 0; text-align: center;
  box-shadow: 0 4px 20px rgba(37,99,235,0.3);
}
.header h1 { font-size: 28px; font-weight: 700; margin-bottom: 8px; }
.header p { font-size: 15px; opacity: 0.9; }
.container { max-width: 1400px; margin: 0 auto; padding: 20px; }
.tabs {
  display: flex; gap: 0; margin: 20px 0 0; border-bottom: 3px solid var(--border);
}
.tab-btn {
  padding: 14px 32px; font-size: 16px; font-weight: 600; cursor: pointer;
  border: none; background: transparent; color: var(--text-light);
  border-bottom: 3px solid transparent; margin-bottom: -3px;
  transition: all 0.3s;
}
.tab-btn:hover { color: var(--primary); }
.tab-btn.active { color: var(--primary); border-bottom-color: var(--primary); }
.tab-content { display: none; }
.tab-content.active { display: block; }
.sub-tabs { display: flex; gap: 8px; margin: 20px 0 16px; flex-wrap: wrap; }
.sub-tab-btn {
  padding: 8px 20px; font-size: 14px; cursor: pointer;
  border: 2px solid var(--border); background: var(--card); color: var(--text-light);
  border-radius: 20px; transition: all 0.2s; font-weight: 500;
}
.sub-tab-btn:hover { border-color: var(--primary-light); color: var(--primary); }
.sub-tab-btn.active { background: var(--primary); color: white; border-color: var(--primary); }
.sub-tab-content { display: none; }
.sub-tab-content.active { display: block; }
.card {
  background: var(--card); border-radius: var(--radius);
  box-shadow: var(--shadow); padding: 24px; margin-bottom: 20px;
  border: 1px solid var(--border);
}
.card h3 {
  font-size: 18px; margin-bottom: 16px; color: var(--text);
  padding-bottom: 10px; border-bottom: 2px solid var(--border);
}
.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
.grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; }
@media(max-width: 900px) { .grid-2, .grid-3 { grid-template-columns: 1fr; } }
.stats-row { display: flex; gap: 16px; margin-bottom: 20px; flex-wrap: wrap; }
.stat-card {
  flex: 1; min-width: 140px; background: linear-gradient(135deg, #eff6ff, #f0fdf4);
  border-radius: 10px; padding: 16px; text-align: center;
  border: 1px solid var(--border);
}
.stat-card .num { font-size: 28px; font-weight: 700; color: var(--primary); }
.stat-card .label { font-size: 13px; color: var(--text-light); margin-top: 4px; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { padding: 10px 14px; text-align: center; border-bottom: 1px solid var(--border); }
th { background: #f1f5f9; font-weight: 600; color: var(--text); }
tr:hover { background: #f8fafc; }
.best-cell { background: #dcfce7; font-weight: 700; color: #166534; }
.form-group { margin-bottom: 14px; }
.form-group label { display: block; font-size: 13px; font-weight: 600; margin-bottom: 4px; color: var(--text-light); }
.form-group select, .form-group input {
  width: 100%; padding: 8px 12px; border: 2px solid var(--border);
  border-radius: 8px; font-size: 14px; transition: border-color 0.2s;
}
.form-group select:focus, .form-group input:focus { border-color: var(--primary); outline: none; }
.btn {
  padding: 10px 28px; font-size: 15px; font-weight: 600;
  background: var(--primary); color: white; border: none;
  border-radius: 8px; cursor: pointer; transition: all 0.2s;
}
.btn:hover { background: #1d4ed8; transform: translateY(-1px); }
.pred-result {
  margin-top: 16px; padding: 16px; background: #f0fdf4;
  border-radius: 10px; border: 1px solid #bbf7d0;
}
.pred-result h4 { color: #166534; margin-bottom: 10px; }
.pred-item { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #dcfce7; }
.pred-item:last-child { border-bottom: none; }
.pred-label { color: var(--text-light); }
.pred-value { font-weight: 700; color: var(--primary); }
.plot-div { width: 100%; min-height: 400px; }
.plot-div-sm { width: 100%; min-height: 350px; }
.radar-container { display: flex; justify-content: center; margin-top: 16px; }
.compare-controls { display: flex; gap: 12px; align-items: flex-end; flex-wrap: wrap; margin-bottom: 16px; }
.compare-controls .form-group { margin-bottom: 0; min-width: 150px; }
.footer { text-align: center; padding: 30px; color: var(--text-light); font-size: 13px; }
</style>
</head>
<body>

<div class="header">
  <h1>🔋 锂硫电池材料性能预测与分析平台</h1>
  <p>基于机器学习的隔膜填料与基底材料性能评估 | 数据驱动 · 交互式可视化</p>
</div>

<div class="container">
  <div class="tabs">
    <button class="tab-btn active" onclick="switchTab('liquid')">🧪 液态电池</button>
    <button class="tab-btn" onclick="switchTab('solid')">🔧 固态电池</button>
  </div>

  <!-- 液态电池 -->
  <div id="tab-liquid" class="tab-content active">
    <div class="sub-tabs">
      <button class="sub-tab-btn active" onclick="switchSubTab('liquid','overview')">📊 数据总览</button>
      <button class="sub-tab-btn" onclick="switchSubTab('liquid','model')">🤖 模型分析</button>
      <button class="sub-tab-btn" onclick="switchSubTab('liquid','predict')">🎯 性能预测</button>
      <button class="sub-tab-btn" onclick="switchSubTab('liquid','scatter')">📈 预测vs实测</button>
      <button class="sub-tab-btn" onclick="switchSubTab('liquid','compare')">⚖️ 材料对比</button>
    </div>
    <div id="liquid-overview" class="sub-tab-content active"></div>
    <div id="liquid-model" class="sub-tab-content"></div>
    <div id="liquid-predict" class="sub-tab-content"></div>
    <div id="liquid-scatter" class="sub-tab-content"></div>
    <div id="liquid-compare" class="sub-tab-content"></div>
  </div>

  <!-- 固态电池 -->
  <div id="tab-solid" class="tab-content">
    <div class="sub-tabs">
      <button class="sub-tab-btn active" onclick="switchSubTab('solid','overview')">📊 数据总览</button>
      <button class="sub-tab-btn" onclick="switchSubTab('solid','model')">🤖 模型分析</button>
      <button class="sub-tab-btn" onclick="switchSubTab('solid','predict')">🎯 性能预测</button>
      <button class="sub-tab-btn" onclick="switchSubTab('solid','scatter')">📈 预测vs实测</button>
      <button class="sub-tab-btn" onclick="switchSubTab('solid','compare')">⚖️ 材料对比</button>
    </div>
    <div id="solid-overview" class="sub-tab-content active"></div>
    <div id="solid-model" class="sub-tab-content"></div>
    <div id="solid-predict" class="sub-tab-content"></div>
    <div id="solid-scatter" class="sub-tab-content"></div>
    <div id="solid-compare" class="sub-tab-content"></div>
  </div>
</div>

<div class="footer">
  锂硫电池材料性能预测平台 &copy; 2026 | 基于 Random Forest / Gradient Boosting / Ridge / XGBoost 模型
</div>

<script>
// ===== 嵌入数据 =====
const DATA = __DATA_JSON__;

// ===== Tab 切换 =====
let currentType = 'liquid';
function switchTab(type) {
  currentType = type;
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
  event.target.classList.add('active');
  document.getElementById('tab-' + type).classList.add('active');
  renderAll(type);
}

function switchSubTab(type, section) {
  const parent = document.getElementById('tab-' + type);
  parent.querySelectorAll('.sub-tab-btn').forEach(b => b.classList.remove('active'));
  parent.querySelectorAll('.sub-tab-content').forEach(c => c.classList.remove('active'));
  event.target.classList.add('active');
  document.getElementById(type + '-' + section).classList.add('active');
  renderSection(type, section);
}

// ===== 渲染入口 =====
const rendered = {};
function renderAll(type) {
  ['overview','model','predict','scatter','compare'].forEach(s => renderSection(type, s));
}
function renderSection(type, section) {
  const key = type + '-' + section;
  if (rendered[key]) return;
  rendered[key] = true;
  const el = document.getElementById(key);
  if (section === 'overview') renderOverview(type, el);
  else if (section === 'model') renderModel(type, el);
  else if (section === 'predict') renderPredict(type, el);
  else if (section === 'scatter') renderScatter(type, el);
  else if (section === 'compare') renderCompare(type, el);
}

// ===== 颜色 =====
const COLORS = ['#2563eb','#10b981','#f59e0b','#ef4444','#8b5cf6','#ec4899','#06b6d4','#84cc16'];
const plotLayout = { font: { family: 'PingFang SC, Microsoft YaHei, sans-serif', size: 13 }, paper_bgcolor: 'rgba(0,0,0,0)', plot_bgcolor: 'rgba(0,0,0,0)', margin: {t:40,b:60,l:60,r:30} };
const plotConfig = { responsive: true, displayModeBar: true, displaylogo: false };

// ===== 1. 数据总览 =====
function renderOverview(type, el) {
  const d = DATA[type];
  const stats = d.stats;
  el.innerHTML = '';

  // 统计卡片
  const row = document.createElement('div');
  row.className = 'stats-row';
  const cards = [
    {num: stats.n_samples, label: '样本总数'},
    {num: Object.keys(stats.filler_counts).length, label: '填料种类'},
    {num: Object.keys(stats.category_counts).length, label: '材料类别'},
    {num: stats.substrate_names.length, label: '基底材料'},
    {num: d.targets.length, label: '目标属性'},
  ];
  cards.forEach(c => {
    const div = document.createElement('div');
    div.className = 'stat-card';
    div.innerHTML = `<div class="num">${c.num}</div><div class="label">${c.label}</div>`;
    row.appendChild(div);
  });
  el.appendChild(row);

  // 特征分布
  const card1 = document.createElement('div');
  card1.className = 'card';
  card1.innerHTML = '<h3>📊 特征分布直方图</h3>';
  const numCols = stats.numeric_cols.filter(c => !['穿梭因子','电化学窗口(V)'].includes(c) || type === (c==='电化学窗口(V)'?'solid':'liquid'));
  const selDiv = document.createElement('div');
  selDiv.style.marginBottom = '12px';
  const sel = document.createElement('select');
  sel.style.cssText = 'padding:8px 12px;border:2px solid #e2e8f0;border-radius:8px;font-size:14px;';
  numCols.forEach(c => { const o = document.createElement('option'); o.value = c; o.text = c; sel.appendChild(o); });
  selDiv.appendChild(sel);
  card1.appendChild(selDiv);
  const histPlot = document.createElement('div');
  histPlot.className = 'plot-div-sm';
  card1.appendChild(histPlot);
  el.appendChild(card1);

  function drawHist(col) {
    const s = stats.feature_stats[col];
    const centers = [];
    for (let i = 0; i < s.hist.length; i++) centers.push((s.hist_edges[i] + s.hist_edges[i+1]) / 2);
    Plotly.newPlot(histPlot, [{x: centers, y: s.hist, type: 'bar', marker: {color: '#3b82f6', opacity: 0.8}, name: col}],
      {...plotLayout, title: col + ' 分布', xaxis: {title: col}, yaxis: {title: '频数'}}, plotConfig);
  }
  sel.onchange = () => drawHist(sel.value);
  drawHist(numCols[0]);

  // 相关性矩阵 + 材料分布
  const grid = document.createElement('div');
  grid.className = 'grid-2';

  const card2 = document.createElement('div');
  card2.className = 'card';
  card2.innerHTML = '<h3>🔗 相关性矩阵</h3>';
  const corrPlot = document.createElement('div');
  corrPlot.className = 'plot-div';
  card2.appendChild(corrPlot);
  grid.appendChild(card2);

  const corr = stats.corr_matrix;
  Plotly.newPlot(corrPlot, [{z: corr.values, x: corr.columns.map(c=>c.length>10?c.slice(0,10)+'…':c), y: corr.columns, type: 'heatmap',
    colorscale: [[0,'#ef4444'],[0.5,'#ffffff'],[1,'#2563eb']], zmin:-1, zmax:1,
    text: corr.values.map(r=>r.map(v=>v.toFixed(2))), texttemplate:'%{text}', textfont:{size:10}}],
    {...plotLayout, title:'特征相关性矩阵', margin:{t:40,b:120,l:120,r:30}}, plotConfig);

  const card3 = document.createElement('div');
  card3.className = 'card';
  card3.innerHTML = '<h3>🥧 材料类别分布</h3>';
  const piePlot = document.createElement('div');
  piePlot.className = 'plot-div';
  card3.appendChild(piePlot);
  grid.appendChild(card3);

  const catLabels = Object.keys(stats.category_counts);
  const catValues = Object.values(stats.category_counts);
  Plotly.newPlot(piePlot, [{labels: catLabels, values: catValues, type: 'pie', hole: 0.4,
    marker: {colors: COLORS}, textinfo: 'label+percent', textfont: {size: 12}}],
    {...plotLayout, title: '填料类别分布', showlegend: false}, plotConfig);

  el.appendChild(grid);
}

// ===== 2. 模型分析 =====
function renderModel(type, el) {
  const d = DATA[type];
  const metrics = d.models.metrics;
  const fi = d.models.feature_importances;
  const bestModels = d.models.best_models;
  el.innerHTML = '';

  // 性能对比表
  const card1 = document.createElement('div');
  card1.className = 'card';
  card1.innerHTML = '<h3>📋 模型性能对比</h3>';
  let tableHtml = '<table><tr><th>目标属性</th><th>模型</th><th>R²</th><th>MAE</th><th>RMSE</th><th>CV R²</th></tr>';
  for (const target of d.targets) {
    if (!metrics[target]) continue;
    const bm = bestModels[target];
    let first = true;
    for (const [mname, m] of Object.entries(metrics[target])) {
      const isBest = mname === bm;
      tableHtml += `<tr>`;
      if (first) { tableHtml += `<td rowspan="${Object.keys(metrics[target]).length}" style="font-weight:600;text-align:left;">${target}<br><small style="color:#10b981;">最优: ${bm}</small></td>`; first = false; }
      tableHtml += `<td>${mname}</td>`;
      tableHtml += `<td class="${isBest?'best-cell':''}">${m.r2.toFixed(4)}</td>`;
      tableHtml += `<td>${m.mae.toFixed(4)}</td>`;
      tableHtml += `<td>${m.rmse.toFixed(4)}</td>`;
      tableHtml += `<td>${m.cv_r2_mean.toFixed(4)}±${m.cv_r2_std.toFixed(4)}</td>`;
      tableHtml += `</tr>`;
    }
  }
  tableHtml += '</table>';
  card1.innerHTML += tableHtml;
  el.appendChild(card1);

  // 特征重要性
  const grid = document.createElement('div');
  grid.className = 'grid-2';

  const card2 = document.createElement('div');
  card2.className = 'card';
  card2.innerHTML = '<h3>📊 特征重要性 (按目标)</h3>';
  const fiSel = document.createElement('select');
  fiSel.style.cssText = 'padding:8px 12px;border:2px solid #e2e8f0;border-radius:8px;font-size:14px;margin-bottom:12px;';
  d.targets.forEach(t => { if(fi[t]) { const o = document.createElement('option'); o.value = t; o.text = t; fiSel.appendChild(o); }});
  card2.appendChild(fiSel);
  const fiPlot = document.createElement('div');
  fiPlot.className = 'plot-div';
  card2.appendChild(fiPlot);
  grid.appendChild(card2);

  function drawFI(target) {
    const imp = fi[target];
    const sorted = Object.entries(imp).sort((a,b) => b[1]-a[1]);
    Plotly.newPlot(fiPlot, [{y: sorted.map(s=>s[0]), x: sorted.map(s=>s[1]), type:'bar', orientation:'h',
      marker:{color: sorted.map((_,i)=>COLORS[i%COLORS.length])}}],
      {...plotLayout, title: target + ' - 特征重要性', xaxis:{title:'重要性'}, yaxis:{automargin:true}}, plotConfig);
  }
  fiSel.onchange = () => drawFI(fiSel.value);
  drawFI(fiSel.options[0].value);

  // 特征重要性热力图
  const card3 = document.createElement('div');
  card3.className = 'card';
  card3.innerHTML = '<h3>🔥 特征重要性热力图</h3>';
  const heatPlot = document.createElement('div');
  heatPlot.className = 'plot-div';
  card3.appendChild(heatPlot);
  grid.appendChild(card3);

  const impSummary = d.models.importance_summary;
  const heatTargets = impSummary.features ? Object.keys(impSummary.values).filter(k=>k!=='平均重要性') : [];
  if (impSummary.features && heatTargets.length > 0) {
    const zData = heatTargets.map(t => impSummary.values[t]);
    const zTransposed = zData[0].map((_,i) => zData.map(row => row[i]));
    Plotly.newPlot(heatPlot, [{z: zTransposed, x: heatTargets.map(t=>t.length>12?t.slice(0,12)+'…':t), y: impSummary.features,
      type:'heatmap', colorscale:'YlOrRd', text: zTransposed.map(r=>r.map(v=>v.toFixed(3))), texttemplate:'%{text}', textfont:{size:10}}],
      {...plotLayout, title:'特征重要性热力图', margin:{t:40,b:120,l:140,r:30}}, plotConfig);
  }

  el.appendChild(grid);
}

// ===== 3. 性能预测 =====
function renderPredict(type, el) {
  const d = DATA[type];
  el.innerHTML = '';

  const card = document.createElement('div');
  card.className = 'card';
  card.innerHTML = '<h3>🎯 性能预测器 (基于Ridge模型系数)</h3>';

  const form = document.createElement('div');
  form.className = 'grid-3';

  // 填料选择
  const fg1 = document.createElement('div');
  fg1.className = 'form-group';
  fg1.innerHTML = '<label>填料类型</label>';
  const sel1 = document.createElement('select');
  sel1.id = type + '-pred-filler';
  d.stats.filler_names.forEach(f => { const o = document.createElement('option'); o.value = f; o.text = f; sel1.appendChild(o); });
  fg1.appendChild(sel1);
  form.appendChild(fg1);

  // 基底选择
  const fg2 = document.createElement('div');
  fg2.className = 'form-group';
  fg2.innerHTML = '<label>基底材料</label>';
  const sel2 = document.createElement('select');
  sel2.id = type + '-pred-sub';
  d.stats.substrate_names.forEach(s => { const o = document.createElement('option'); o.value = s; o.text = s; sel2.appendChild(o); });
  fg2.appendChild(sel2);
  form.appendChild(fg2);

  // 数值参数
  const numFeatures = d.features.filter(f => !['填料类型','填料类别','基底材料','基底/聚合物','电解液体系'].includes(f));
  const defaults = type === 'liquid'
    ? {'填料负载量(mg/cm²)':2.0,'比表面积(m²/g)':200,'粒径(nm)':30,'孔体积(cm³/g)':0.5,'隔膜厚度(μm)':25,'孔隙率':0.4,'温度(°C)':25,'倍率(C)':0.5,'循环次数':100}
    : {'填料含量(wt%)':10,'比表面积(m²/g)':100,'粒径(nm)':30,'膜厚度(μm)':30,'温度(°C)':25,'压力(MPa)':0.3,'倍率(C)':0.5,'循环次数':100};

  numFeatures.forEach(f => {
    const fg = document.createElement('div');
    fg.className = 'form-group';
    fg.innerHTML = `<label>${f}</label>`;
    const inp = document.createElement('input');
    inp.type = 'number'; inp.step = 'any';
    inp.id = type + '-pred-' + f;
    inp.value = defaults[f] || 0;
    fg.appendChild(inp);
    form.appendChild(fg);
  });

  card.appendChild(form);

  const btnDiv = document.createElement('div');
  btnDiv.style.cssText = 'margin-top:16px;text-align:center;';
  const btn = document.createElement('button');
  btn.className = 'btn';
  btn.textContent = '🚀 开始预测';
  btn.onclick = () => doPredict(type);
  btnDiv.appendChild(btn);
  card.appendChild(btnDiv);

  const resultDiv = document.createElement('div');
  resultDiv.id = type + '-pred-result';
  card.appendChild(resultDiv);

  el.appendChild(card);
}

function doPredict(type) {
  const d = DATA[type];
  const coeffs = d.coeffs;
  const leMap = d.le_map;
  const features = d.features;

  // 构建特征向量
  const vals = [];
  features.forEach(f => {
    if (leMap[f]) {
      const sel = document.getElementById(type + '-pred-' + (f==='填料类型'?'filler':f==='基底材料'||f==='基底/聚合物'?'sub':''));
      let v = 0;
      if (f === '填料类型') v = document.getElementById(type+'-pred-filler').value;
      else if (f === '基底材料' || f === '基底/聚合物') v = document.getElementById(type+'-pred-sub').value;
      else if (f === '填料类别') {
        const fillerName = document.getElementById(type+'-pred-filler').value;
        v = d.stats.filler_categories[fillerName] || '';
      }
      else if (f === '电解液体系') v = 'LiTFSI/DOL-DME';
      vals.push(leMap[f][v] !== undefined ? leMap[f][v] : 0);
    } else {
      const inp = document.getElementById(type + '-pred-' + f);
      vals.push(inp ? parseFloat(inp.value) || 0 : 0);
    }
  });

  // 预测
  const resultDiv = document.getElementById(type + '-pred-result');
  let html = '<div class="pred-result"><h4>📊 预测结果</h4>';

  for (const target of d.targets) {
    if (!coeffs[target]) continue;
    const c = coeffs[target];
    // 标准化
    const scaled = vals.map((v,i) => (v - c.scaler_mean[i]) / c.scaler_scale[i]);
    let pred = c.intercept + scaled.reduce((s,v,i) => s + v * c.coef[i], 0);
    if (c.use_log) pred = Math.pow(10, pred);
    const unit = target.includes('(') ? target.match(/\(([^)]+)\)/)[1] : '';
    html += `<div class="pred-item"><span class="pred-label">${target}</span><span class="pred-value">${pred.toFixed(4)}</span></div>`;
  }
  html += '</div>';
  resultDiv.innerHTML = html;
}

// ===== 4. 预测vs实测 =====
function renderScatter(type, el) {
  const d = DATA[type];
  const preds = d.models.predictions;
  el.innerHTML = '';

  const card = document.createElement('div');
  card.className = 'card';
  card.innerHTML = '<h3>📈 预测值 vs 实测值</h3>';

  const selDiv = document.createElement('div');
  selDiv.style.marginBottom = '12px';
  const sel = document.createElement('select');
  sel.style.cssText = 'padding:8px 12px;border:2px solid #e2e8f0;border-radius:8px;font-size:14px;';
  d.targets.forEach(t => { if(preds[t]) { const o = document.createElement('option'); o.value = t; o.text = t; sel.appendChild(o); }});
  selDiv.appendChild(sel);
  card.appendChild(selDiv);

  const plotDiv = document.createElement('div');
  plotDiv.className = 'plot-div';
  card.appendChild(plotDiv);
  el.appendChild(card);

  function drawScatter(target) {
    const p = preds[target];
    const allActual = [...p.y_train, ...p.y_test];
    const allPred = [...p.y_pred_train, ...p.y_pred_test];
    const mn = Math.min(...allActual, ...allPred);
    const mx = Math.max(...allActual, ...allPred);
    const traces = [
      {x: p.y_train, y: p.y_pred_train, mode:'markers', type:'scatter', name:'训练集',
       marker:{color:'#10b981',size:5,opacity:0.6}},
      {x: p.y_test, y: p.y_pred_test, mode:'markers', type:'scatter', name:'测试集',
       marker:{color:'#ef4444',size:6,opacity:0.8}},
      {x:[mn,mx], y:[mn,mx], mode:'lines', type:'scatter', name:'y=x',
       line:{color:'#64748b',dash:'dash',width:2}},
    ];
    Plotly.newPlot(plotDiv, traces,
      {...plotLayout, title: target + ' - 预测vs实测', xaxis:{title:'实测值'}, yaxis:{title:'预测值'},
       legend:{x:0.02,y:0.98}}, plotConfig);
  }
  sel.onchange = () => drawScatter(sel.value);
  drawScatter(sel.options[0].value);
}

// ===== 5. 材料对比 =====
function renderCompare(type, el) {
  const d = DATA[type];
  el.innerHTML = '';

  const card = document.createElement('div');
  card.className = 'card';
  card.innerHTML = '<h3>⚖️ 多材料性能对比</h3>';

  // 选择材料
  const ctrl = document.createElement('div');
  ctrl.className = 'compare-controls';
  const fg = document.createElement('div');
  fg.className = 'form-group';
  fg.innerHTML = '<label>选择材料 (最多5个，逗号分隔)</label>';
  const inp = document.createElement('input');
  inp.type = 'text';
  inp.value = d.stats.filler_names.slice(0, 4).join(', ');
  inp.id = type + '-compare-input';
  inp.style.minWidth = '400px';
  fg.appendChild(inp);
  ctrl.appendChild(fg);

  const btn = document.createElement('button');
  btn.className = 'btn';
  btn.textContent = '📊 对比分析';
  btn.onclick = () => drawCompare(type);
  ctrl.appendChild(btn);
  card.appendChild(ctrl);

  const barPlot = document.createElement('div');
  barPlot.className = 'plot-div';
  barPlot.id = type + '-compare-bar';
  card.appendChild(barPlot);

  const radarPlot = document.createElement('div');
  radarPlot.className = 'plot-div';
  radarPlot.id = type + '-compare-radar';
  card.appendChild(radarPlot);

  el.appendChild(card);
  drawCompare(type);
}

function drawCompare(type) {
  const d = DATA[type];
  const input = document.getElementById(type + '-compare-input').value;
  const materials = input.split(',').map(s => s.trim()).filter(s => s).slice(0, 5);
  if (materials.length < 2) return;

  const coeffs = d.coeffs;
  const leMap = d.le_map;
  const features = d.features;

  // 对每个材料做预测
  const predictions = {};
  materials.forEach(mat => {
    predictions[mat] = {};
    const defaults = type === 'liquid'
      ? {'填料负载量(mg/cm²)':2.0,'比表面积(m²/g)':200,'粒径(nm)':30,'孔体积(cm³/g)':0.5,'隔膜厚度(μm)':25,'孔隙率':0.4,'温度(°C)':25,'倍率(C)':0.5,'循环次数':100}
      : {'填料含量(wt%)':10,'比表面积(m²/g)':100,'粒径(nm)':30,'膜厚度(μm)':30,'温度(°C)':25,'压力(MPa)':0.3,'倍率(C)':0.5,'循环次数':100};

    // 获取填料的固有属性
    const fillerKey = mat;
    const fillers = type === 'liquid' ? DATA.liquid.stats : DATA.solid.stats;

    for (const target of d.targets) {
      if (!coeffs[target]) continue;
      const c = coeffs[target];
      const vals = features.map(f => {
        if (f === '填料类型') return leMap[f][mat] !== undefined ? leMap[f][mat] : 0;
        if (f === '填料类别') {
          const cat = fillers.filler_categories[mat] || '';
          return leMap[f] && leMap[f][cat] !== undefined ? leMap[f][cat] : 0;
        }
        if (f === '基底材料' || f === '基底/聚合物') {
          const sub = fillers.substrate_names[0] || '';
          return leMap[f] && leMap[f][sub] !== undefined ? leMap[f][sub] : 0;
        }
        if (f === '电解液体系') return leMap[f] && leMap[f]['LiTFSI/DOL-DME'] !== undefined ? leMap[f]['LiTFSI/DOL-DME'] : 0;
        return defaults[f] || 0;
      });
      const scaled = vals.map((v,i) => (v - c.scaler_mean[i]) / c.scaler_scale[i]);
      let pred = c.intercept + scaled.reduce((s,v,i) => s + v * c.coef[i], 0);
      if (c.use_log) pred = Math.pow(10, pred);
      predictions[mat][target] = pred;
    }
  });

  // 柱状图
  const targets = d.targets.filter(t => coeffs[t]);
  const traces = [];
  materials.forEach((mat, i) => {
    traces.push({
      x: targets.map(t => t.length > 14 ? t.slice(0,14)+'…' : t),
      y: targets.map(t => predictions[mat][t] || 0),
      type: 'bar', name: mat,
      marker: {color: COLORS[i % COLORS.length], opacity: 0.85},
    });
  });

  Plotly.newPlot(type + '-compare-bar', traces,
    {...plotLayout, title: '多材料性能预测对比', barmode: 'group',
     xaxis: {title: '性能指标', tickangle: -30}, yaxis: {title: '预测值'}}, plotConfig);

  // 雷达图 (归一化)
  const radarTraces = [];
  // 计算每个target的最大最小值用于归一化
  const minMax = {};
  targets.forEach(t => {
    const vals = materials.map(m => predictions[m][t] || 0);
    minMax[t] = {min: Math.min(...vals) * 0.9, max: Math.max(...vals) * 1.1 || 1};
  });

  materials.forEach((mat, i) => {
    const normVals = targets.map(t => {
      const v = predictions[mat][t] || 0;
      const range = minMax[t].max - minMax[t].min || 1;
      return ((v - minMax[t].min) / range) * 100;
    });
    radarTraces.push({
      type: 'scatterpolar',
      r: [...normVals, normVals[0]],
      theta: [...targets.map(t => t.length > 14 ? t.slice(0,14)+'…' : t), targets[0].length > 14 ? targets[0].slice(0,14)+'…' : targets[0]],
      fill: 'toself', name: mat, opacity: 0.6,
      line: {color: COLORS[i % COLORS.length]},
    });
  });

  Plotly.newPlot(type + '-compare-radar', radarTraces,
    {...plotLayout, title: '多材料雷达对比图',
     polar: {radialaxis: {visible: true, range: [0, 100]}},
     showlegend: true, legend: {x: 1.1, y: 1}}, plotConfig);
}

// ===== 初始化 =====
renderAll('liquid');
</script>
</body>
</html>'''

# 注入数据
data_json = json.dumps(all_data, ensure_ascii=False)
html_content = html_template.replace('__DATA_JSON__', data_json)

output_path = '/share/bf/lis_battery_platform/report.html'
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(html_content)

file_size = os.path.getsize(output_path) / 1024
print(f"\n✅ 报告已生成: {output_path}")
print(f"   文件大小: {file_size:.1f} KB")
print(f"   液态样本: {liquid_stats['n_samples']}, 固态样本: {solid_stats['n_samples']}")
print(f"   液态目标: {LIQUID_TARGETS}")
print(f"   固态目标: {SOLID_TARGETS}")
