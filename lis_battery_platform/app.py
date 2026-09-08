"""
锂硫电池隔膜填料与适配基底材料设计 - 数据预测分析交互平台
========================================================
区分固态电池和液态电池，模型以数据真实可解释优先
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys
import os
import warnings
warnings.filterwarnings('ignore')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate_data import (generate_all_data, LIQUID_FILLERS, LIQUID_SUBSTRATES,
                           LIQUID_ELECTROLYTES, SOLID_FILLERS, SOLID_SUBSTRATES)
from modeling import (train_models, predict_single, get_feature_importance_summary,
                      LIQUID_FEATURES, LIQUID_TARGETS, SOLID_FEATURES, SOLID_TARGETS)
from material_kb import (EXTENDED_LIQUID_KB, EXTENDED_SOLID_KB,
                          search_material, search_training_kb,
                          get_recommended_config)

# ============================================================
# 页面配置
# ============================================================
st.set_page_config(
    page_title="锂硫电池隔膜材料设计平台",
    page_icon="🔋",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1a1a2e;
        text-align: center;
        padding: 0.5rem 0;
        border-bottom: 3px solid #16213e;
        margin-bottom: 1rem;
    }
    .sub-header {
        font-size: 1.4rem;
        font-weight: 600;
        color: #16213e;
        padding: 0.3rem 0;
        border-left: 4px solid #0f3460;
        padding-left: 1rem;
        margin: 1rem 0 0.5rem 0;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 20px;
        border-radius: 8px 8px 0 0;
    }
    .prediction-box {
        background: #f0f4ff;
        border: 2px solid #4361ee;
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    .actual-box {
        background: #f0fff4;
        border: 2px solid #2ecc71;
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================
# 缓存数据生成和模型训练
# ============================================================
@st.cache_data
def load_data():
    liquid_df, solid_df = generate_all_data()
    return liquid_df, solid_df

@st.cache_resource
def train_all_models(_liquid_df, _solid_df):
    liquid_results, liquid_encoders, liquid_scaler = train_models(
        _liquid_df, LIQUID_FEATURES, LIQUID_TARGETS
    )
    solid_results, solid_encoders, solid_scaler = train_models(
        _solid_df, SOLID_FEATURES, SOLID_TARGETS
    )
    return (liquid_results, liquid_encoders, liquid_scaler,
            solid_results, solid_encoders, solid_scaler)

# 加载数据和模型
with st.spinner("正在生成材料数据库..."):
    liquid_df, solid_df = load_data()

with st.spinner("正在训练预测模型（首次加载需要约30秒）..."):
    (liquid_results, liquid_encoders, liquid_scaler,
     solid_results, solid_encoders, solid_scaler) = train_all_models(liquid_df, solid_df)

# ============================================================
# 侧边栏
# ============================================================
st.markdown('<div class="main-header">🔋 锂硫电池隔膜填料与基底材料设计平台</div>', 
            unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### ⚙️ 系统设置")
    
    battery_type = st.radio(
        "🔋 电池类型",
        ["液态锂硫电池", "固态锂硫电池"],
        index=0,
        help="选择电池类型以切换数据集和模型"
    )
    
    st.markdown("---")
    st.markdown("### 📊 数据概览")
    if battery_type == "液态锂硫电池":
        st.metric("样本总数", f"{len(liquid_df)}")
        st.metric("填料种类", f"{len(LIQUID_FILLERS)}")
        st.metric("基底种类", f"{len(LIQUID_SUBSTRATES)}")
        st.metric("电解液体系", f"{len(LIQUID_ELECTROLYTES)}")
    else:
        st.metric("样本总数", f"{len(solid_df)}")
        st.metric("填料种类", f"{len(SOLID_FILLERS)}")
        st.metric("基底/聚合物种类", f"{len(SOLID_SUBSTRATES)}")
    
    st.markdown("---")
    st.markdown("### 📋 关于")
    st.markdown("""
    **数据来源**: 基于文献报道的真实物理化学关系编码生成  
    **模型方法**: Random Forest / Gradient Boosting / Ridge Regression  
    **可解释性**: SHAP特征重要性 + 物理关系验证  
    **样本量**: 1250条（液态650 + 固态600）
    """)

# 选择当前数据集
is_liquid = (battery_type == "液态锂硫电池")
current_df = liquid_df if is_liquid else solid_df
current_results = liquid_results if is_liquid else solid_results
current_encoders = liquid_encoders if is_liquid else solid_encoders
current_scaler = liquid_scaler if is_liquid else solid_scaler
current_features = LIQUID_FEATURES if is_liquid else SOLID_FEATURES
current_targets = LIQUID_TARGETS if is_liquid else SOLID_TARGETS
battery_emoji = "💧" if is_liquid else "🧊"

# ============================================================
# 主标签页
# ============================================================
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 数据总览", "🤖 模型分析", "🎯 性能预测",
    "🔍 预测vs实测", "⚖️ 材料对比", "🧪 自定义材料分析"
])

# ============================================================
# TAB 1: 数据总览
# ============================================================
with tab1:
    st.markdown(f'<div class="sub-header">{battery_emoji} {battery_type} — 数据总览</div>', 
                unsafe_allow_html=True)
    
    # 统计卡片
    cols = st.columns(4)
    cols[0].metric("样本数", len(current_df))
    if is_liquid:
        cols[1].metric("平均初始容量", f"{current_df['初始比容量(mAh/g)'].mean():.0f} mAh/g")
        cols[2].metric("平均库伦效率", f"{current_df['库伦效率(%)'].mean():.1f}%")
        cols[3].metric("平均容量保持率", f"{current_df['容量保持率(%)'].mean():.1f}%")
    else:
        cols[1].metric("平均初始容量", f"{current_df['初始比容量(mAh/g)'].mean():.0f} mAh/g")
        cols[2].metric("平均界面阻抗", f"{current_df['界面阻抗(Ω·cm²)'].mean():.0f} Ω·cm²")
        cols[3].metric("平均电化学窗口", f"{current_df['电化学窗口(V)'].mean():.2f} V")
    
    st.markdown("#### 📈 特征分布")
    
    # 特征分布图
    if is_liquid:
        num_features = ['填料负载量(mg/cm²)', '比表面积(m²/g)', '粒径(nm)', 
                       '孔体积(cm³/g)', '隔膜厚度(μm)', '孔隙率']
        target_features = ['离子电导率(mS/cm)', '初始比容量(mAh/g)', '容量保持率(%)', 
                          '库伦效率(%)', '穿梭因子']
    else:
        num_features = ['填料含量(wt%)', '比表面积(m²/g)', '粒径(nm)',
                       '膜厚度(μm)', '温度(°C)', '压力(MPa)']
        target_features = ['离子电导率(mS/cm)', '界面阻抗(Ω·cm²)', '初始比容量(mAh/g)',
                          '容量保持率(%)', '库伦效率(%)', '电化学窗口(V)']
    
    # 分布直方图
    selected_dist = st.selectbox("选择特征查看分布", num_features + target_features, key="dist_select")
    col1, col2 = st.columns(2)
    with col1:
        fig_hist = px.histogram(current_df, x=selected_dist, nbins=40,
                                color_discrete_sequence=['#4361ee'],
                                title=f"{selected_dist} 分布")
        fig_hist.update_layout(bargap=0.05)
        st.plotly_chart(fig_hist, use_container_width=True)
    with col2:
        fig_box = px.box(current_df, y=selected_dist,
                        color_discrete_sequence=['#e74c3c'],
                        title=f"{selected_dist} 箱线图")
        st.plotly_chart(fig_box, use_container_width=True)
    
    # 分类统计
    st.markdown("#### 🏷️ 材料分布统计")
    col1, col2, col3 = st.columns(3)
    
    if is_liquid:
        with col1:
            cat_counts = current_df['填料类别'].value_counts()
            fig_cat = px.pie(values=cat_counts.values, names=cat_counts.index,
                           title="填料类别分布", hole=0.3,
                           color_discrete_sequence=px.colors.qualitative.Set2)
            st.plotly_chart(fig_cat, use_container_width=True)
        with col2:
            sub_counts = current_df['基底材料'].value_counts().head(8)
            fig_sub = px.bar(x=sub_counts.values, y=sub_counts.index, orientation='h',
                           title="基底材料分布(Top 8)",
                           color_discrete_sequence=['#2ecc71'])
            fig_sub.update_layout(yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig_sub, use_container_width=True)
        with col3:
            elec_counts = current_df['电解液体系'].value_counts()
            fig_elec = px.pie(values=elec_counts.values, names=elec_counts.index,
                            title="电解液体系分布", hole=0.3,
                            color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_elec, use_container_width=True)
    else:
        with col1:
            cat_counts = current_df['填料类别'].value_counts()
            fig_cat = px.pie(values=cat_counts.values, names=cat_counts.index,
                           title="填料类别分布", hole=0.3,
                           color_discrete_sequence=px.colors.qualitative.Set2)
            st.plotly_chart(fig_cat, use_container_width=True)
        with col2:
            sub_counts = current_df['基底/聚合物'].value_counts().head(8)
            fig_sub = px.bar(x=sub_counts.values, y=sub_counts.index, orientation='h',
                           title="基底/聚合物分布(Top 8)",
                           color_discrete_sequence=['#2ecc71'])
            fig_sub.update_layout(yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig_sub, use_container_width=True)
        with col3:
            filler_counts = current_df['填料类型'].value_counts().head(10)
            fig_fill = px.bar(x=filler_counts.values, y=filler_counts.index, orientation='h',
                            title="填料类型分布(Top 10)",
                            color_discrete_sequence=['#9b59b6'])
            fig_fill.update_layout(yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig_fill, use_container_width=True)
    
    # 相关性矩阵
    st.markdown("#### 🔗 特征相关性矩阵")
    numeric_cols = current_df.select_dtypes(include=[np.number]).columns.tolist()
    corr = current_df[numeric_cols].corr()
    fig_corr = px.imshow(corr, text_auto=".2f", aspect="auto",
                         color_continuous_scale='RdBu_r', zmin=-1, zmax=1,
                         title="数值特征相关性矩阵")
    fig_corr.update_layout(height=600)
    st.plotly_chart(fig_corr, use_container_width=True)
    
    # 数据表
    with st.expander("📋 查看原始数据表"):
        st.dataframe(current_df, use_container_width=True, height=400)
        csv = current_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 下载CSV数据",
            data=csv,
            file_name=f"{'liquid' if is_liquid else 'solid'}_battery_data.csv",
            mime="text/csv"
        )

# ============================================================
# TAB 2: 模型分析
# ============================================================
with tab2:
    st.markdown(f'<div class="sub-header">🤖 {battery_type} — 模型分析与可解释性</div>', 
                unsafe_allow_html=True)
    
    # 模型性能对比
    st.markdown("#### 📊 模型性能对比")
    
    metrics_data = []
    for target in current_targets:
        if target not in current_results:
            continue
        target_res = current_results[target]
        for model_name in target_res:
            if model_name == 'best_model':
                continue
            r = target_res[model_name]
            metrics_data.append({
                '目标变量': target,
                '模型': model_name,
                'MAE': f"{r['mae']:.4f}",
                'RMSE': f"{r['rmse']:.4f}",
                'R²': f"{r['r2']:.4f}",
                'CV-R²(均值±标准差)': f"{r['cv_r2_mean']:.4f} ± {r['cv_r2_std']:.4f}",
                '最佳': '⭐' if model_name == target_res['best_model'] else ''
            })
    
    metrics_df = pd.DataFrame(metrics_data)
    st.dataframe(metrics_df, use_container_width=True, hide_index=True)
    
    # 特征重要性
    st.markdown("#### 🎯 特征重要性分析（Random Forest）")
    
    selected_target = st.selectbox("选择目标变量", current_targets, key="fi_target")
    
    if selected_target in current_results:
        target_res = current_results[selected_target]
        
        # 获取最佳模型的特征重要性
        best_name = target_res['best_model']
        importances = target_res[best_name]['feature_importances']
        
        # 排序
        imp_sorted = sorted(importances.items(), key=lambda x: x[1], reverse=True)
        imp_df = pd.DataFrame(imp_sorted, columns=['特征', '重要性'])
        
        col1, col2 = st.columns([3, 2])
        with col1:
            fig_imp = px.bar(imp_df, x='重要性', y='特征', orientation='h',
                           title=f"{selected_target} — 特征重要性 ({best_name})",
                           color='重要性', color_continuous_scale='Blues')
            fig_imp.update_layout(yaxis={'categoryorder': 'total ascending'}, height=450)
            st.plotly_chart(fig_imp, use_container_width=True)
        
        with col2:
            st.markdown("##### 📝 物理解读")
            top3 = imp_df.head(3)
            for idx, row in top3.iterrows():
                st.markdown(f"**{row['特征']}** (重要性: {row['重要性']:.3f})")
                # 添加物理解释
                if '比表面积' in row['特征']:
                    st.markdown("  → 高比表面积提供更多多硫化物吸附位点/离子传输通道")
                elif '填料' in row['特征'] and '类型' in row['特征']:
                    st.markdown("  → 不同填料的化学吸附能力和导电性差异显著")
                elif '循环' in row['特征']:
                    st.markdown("  → 循环次数直接反映电池寿命和退化程度")
                elif '倍率' in row['特征']:
                    st.markdown("  → 高倍率下动力学限制导致性能下降")
                elif '温度' in row['特征']:
                    st.markdown("  → 温度影响离子迁移速率和界面反应动力学")
                elif '孔隙率' in row['特征']:
                    st.markdown("  → 孔隙率影响电解液浸润和离子传输")
                elif '压力' in row['特征']:
                    st.markdown("  → 压力改善固态界面接触，降低阻抗")
                elif '粒径' in row['特征']:
                    st.markdown("  → 粒径影响比表面积和界面接触质量")
                else:
                    st.markdown(f"  → 该特征对{selected_target}有显著影响")
        
        # 所有目标的特征重要性热力图
        st.markdown("#### 🗺️ 全目标特征重要性热力图")
        imp_summary = get_feature_importance_summary(current_results, current_features)
        fig_heatmap = px.imshow(imp_summary.drop('平均重要性', axis=1).T,
                               text_auto=".3f", aspect="auto",
                               color_continuous_scale='YlOrRd',
                               title="各目标变量的特征重要性分布")
        fig_heatmap.update_layout(height=400)
        st.plotly_chart(fig_heatmap, use_container_width=True)

# ============================================================
# TAB 3: 性能预测
# ============================================================
with tab3:
    st.markdown(f'<div class="sub-header">🎯 {battery_type} — 材料性能预测</div>', 
                unsafe_allow_html=True)
    
    st.markdown("""
    > 💡 **使用方法**: 在下方选择或调整材料参数，模型将基于训练数据给出预测结果。  
    > 预测值旁标注了模型R²分数和不确定性范围，供参考。
    """)
    
    # 输入参数
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("##### 🔧 填料参数")
        
        if is_liquid:
            filler_options = list(LIQUID_FILLERS.keys())
            selected_filler = st.selectbox("填料类型", filler_options, key="pred_filler")
            filler_info = LIQUID_FILLERS[selected_filler]
            filler_loading = st.slider("填料负载量 (mg/cm²)", 0.05, 3.0, 1.0, 0.05, key="pred_loading")
            sa = st.slider("比表面积 (m²/g)", 5.0, 2000.0, 
                          float(filler_info['sa_base']), 5.0, key="pred_sa")
            ps = st.slider("粒径 (nm)", 1.0, 500.0, 
                          float(filler_info['ps_base']), 1.0, key="pred_ps")
            pv = st.slider("孔体积 (cm³/g)", 0.01, 2.0, 
                          float(filler_info['pv_base']), 0.01, key="pred_pv")
        else:
            filler_options = list(SOLID_FILLERS.keys())
            selected_filler = st.selectbox("填料类型", filler_options, key="pred_filler")
            filler_info = SOLID_FILLERS[selected_filler]
            filler_content = st.slider("填料含量 (wt%)", 10.0, 80.0, 40.0, 1.0, key="pred_content")
            sa = st.slider("比表面积 (m²/g)", 2.0, 500.0, 
                          float(filler_info['sa_base']), 1.0, key="pred_sa")
            ps = st.slider("粒径 (nm)", 10.0, 2000.0, 
                          float(filler_info['ps_base']), 10.0, key="pred_ps")
    
    with col2:
        st.markdown("##### 🔧 基底与工况参数")
        
        if is_liquid:
            substrate_options = list(LIQUID_SUBSTRATES.keys())
            selected_substrate = st.selectbox("基底材料", substrate_options, key="pred_sub")
            sub_info = LIQUID_SUBSTRATES[selected_substrate]
            thickness = st.slider("隔膜厚度 (μm)", 5.0, 700.0, 
                                 float(sub_info['thickness_base']), 1.0, key="pred_thick")
            porosity = st.slider("孔隙率", 0.15, 0.95, 
                                float(sub_info['porosity_base']), 0.01, key="pred_por")
            electrolyte_options = list(LIQUID_ELECTROLYTES.keys())
            selected_electrolyte = st.selectbox("电解液体系", electrolyte_options, key="pred_elec")
            temperature = st.slider("温度 (°C)", 20, 80, 25, 1, key="pred_temp")
            current_rate = st.select_slider("倍率 (C)", [0.1, 0.2, 0.5, 1.0, 2.0, 3.0, 5.0], 0.5, key="pred_rate")
            cycle_number = st.slider("循环次数", 50, 1000, 200, 50, key="pred_cycle")
        else:
            substrate_options = list(SOLID_SUBSTRATES.keys())
            selected_substrate = st.selectbox("基底/聚合物", substrate_options, key="pred_sub")
            sub_info = SOLID_SUBSTRATES[selected_substrate]
            thickness = st.slider("膜厚度 (μm)", 10.0, 200.0, 
                                 float(sub_info['thickness_base']), 1.0, key="pred_thick")
            temperature = st.slider("温度 (°C)", 20, 100, 25, 1, key="pred_temp")
            pressure = st.slider("压力 (MPa)", 50.0, 500.0, 200.0, 10.0, key="pred_press")
            current_rate = st.select_slider("倍率 (C)", [0.05, 0.1, 0.2, 0.5, 1.0], 0.2, key="pred_rate")
            cycle_number = st.slider("循环次数", 50, 800, 200, 50, key="pred_cycle")
    
    # 构建输入特征
    try:
        if is_liquid:
            input_features = {
                '填料类型': selected_filler,
                '填料类别': LIQUID_FILLERS[selected_filler]['category'],
                '填料负载量(mg/cm²)': filler_loading,
                '比表面积(m²/g)': sa,
                '粒径(nm)': ps,
                '孔体积(cm³/g)': pv,
                '基底材料': selected_substrate,
                '隔膜厚度(μm)': thickness,
                '孔隙率': porosity,
                '电解液体系': selected_electrolyte,
                '温度(°C)': temperature,
                '倍率(C)': current_rate,
                '循环次数': cycle_number,
            }
            
            predictions = predict_single(
                liquid_results, liquid_encoders, liquid_scaler,
                LIQUID_FEATURES, LIQUID_TARGETS, input_features, 'liquid'
            )
        else:
            input_features = {
                '填料类型': selected_filler,
                '填料类别': SOLID_FILLERS[selected_filler]['category'],
                '填料含量(wt%)': filler_content,
                '比表面积(m²/g)': sa,
                '粒径(nm)': ps,
                '基底/聚合物': selected_substrate,
                '膜厚度(μm)': thickness,
                '温度(°C)': temperature,
                '压力(MPa)': pressure,
                '倍率(C)': current_rate,
                '循环次数': cycle_number,
            }
            
            predictions = predict_single(
                solid_results, solid_encoders, solid_scaler,
                SOLID_FEATURES, SOLID_TARGETS, input_features, 'solid'
            )
    except Exception as e:
        st.error(f"预测时出错: {e}")
        predictions = {}
    
    if not predictions:
        st.warning("未能生成预测结果，请检查输入参数。")
    
    # 显示预测结果
    st.markdown("---")
    st.markdown("#### 📊 预测结果")
    
    n_preds = len(predictions) if predictions else 1
    pred_cols = st.columns(n_preds)
    for idx, (target, pred_info) in enumerate(predictions.items()):
        with pred_cols[idx]:
            val = pred_info['predicted_value']
            unc = pred_info['uncertainty']
            r2 = pred_info['r2']
            model_name = pred_info['best_model']
            
            # 格式化显示
            if '电导率' in target:
                val_str = f"{val:.4f}"
                unc_str = f"±{unc:.4f}"
            elif '容量' in target or '阻抗' in target:
                val_str = f"{val:.1f}"
                unc_str = f"±{unc:.1f}"
            elif '效率' in target or '保持率' in target or '窗口' in target:
                val_str = f"{val:.2f}"
                unc_str = f"±{unc:.2f}"
            else:
                val_str = f"{val:.4f}"
                unc_str = f"±{unc:.4f}"
            
            # R²颜色指示
            if r2 > 0.8:
                r2_color = "🟢"
            elif r2 > 0.5:
                r2_color = "🟡"
            else:
                r2_color = "🔴"
            
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                        padding: 15px; border-radius: 10px; color: white; text-align: center;">
                <div style="font-size: 0.85rem; opacity: 0.9;">{target}</div>
                <div style="font-size: 1.8rem; font-weight: 700; margin: 5px 0;">{val_str}</div>
                <div style="font-size: 0.8rem; opacity: 0.8;">{unc_str}</div>
                <div style="font-size: 0.75rem; margin-top: 5px;">
                    {r2_color} R²={r2:.3f} | {model_name}
                </div>
            </div>
            """, unsafe_allow_html=True)
    
    # 多模型预测对比
    st.markdown("#### 🔀 多模型预测对比")
    st.markdown("> 不同模型的预测差异反映预测不确定性")
    
    comparison_data = []
    for target, pred_info in predictions.items():
        row = {'目标变量': target, '最佳预测值': pred_info['predicted_value']}
        for model_name, model_pred in pred_info.get('all_model_predictions', {}).items():
            row[model_name] = model_pred
        comparison_data.append(row)
    
    if comparison_data:
        comp_df = pd.DataFrame(comparison_data)
        st.dataframe(comp_df, use_container_width=True, hide_index=True)

# ============================================================
# TAB 4: 预测vs实测
# ============================================================
with tab4:
    st.markdown(f'<div class="sub-header">🔍 {battery_type} — 预测值 vs 实际值对比</div>', 
                unsafe_allow_html=True)
    
    st.markdown("""
    > 📌 **绿色点** = 训练集样本（模型已学习）  
    > 📌 **红色点** = 测试集样本（模型未见过的数据）  
    > 虚线为理想预测线（y=x），点越接近虚线表示预测越准确
    """)
    
    selected_target_pv = st.selectbox("选择目标变量", current_targets, key="pv_target")
    
    if selected_target_pv in current_results:
        target_res = current_results[selected_target_pv]
        best_name = target_res['best_model']
        best_res = target_res[best_name]
        
        y_train = best_res['y_train']
        y_pred_train = best_res['y_pred_train']
        y_test = best_res['y_test']
        y_pred_test = best_res['y_pred_test']
        
        # 散点图
        fig_pv = go.Figure()
        
        # 训练集
        fig_pv.add_trace(go.Scatter(
            x=y_train, y=y_pred_train, mode='markers',
            marker=dict(size=4, color='#2ecc71', opacity=0.4),
            name=f'训练集 (n={len(y_train)})'
        ))
        
        # 测试集
        fig_pv.add_trace(go.Scatter(
            x=y_test, y=y_pred_test, mode='markers',
            marker=dict(size=6, color='#e74c3c', opacity=0.7),
            name=f'测试集 (n={len(y_test)})'
        ))
        
        # 理想线
        all_vals = np.concatenate([y_train, y_test, y_pred_train, y_pred_test])
        min_val, max_val = np.min(all_vals), np.max(all_vals)
        fig_pv.add_trace(go.Scatter(
            x=[min_val, max_val], y=[min_val, max_val],
            mode='lines', line=dict(color='gray', dash='dash', width=2),
            name='理想预测线 (y=x)'
        ))
        
        fig_pv.update_layout(
            title=f"{selected_target_pv} — 预测值 vs 实际值 ({best_name})",
            xaxis_title="实际值",
            yaxis_title="预测值",
            height=550,
            legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01)
        )
        st.plotly_chart(fig_pv, use_container_width=True)
        
        # 误差分布
        col1, col2 = st.columns(2)
        with col1:
            errors_train = y_pred_train - y_train
            errors_test = y_pred_test - y_test
            
            fig_err = go.Figure()
            fig_err.add_trace(go.Histogram(
                x=errors_train, name='训练集误差', 
                marker_color='#2ecc71', opacity=0.6, nbinsx=30
            ))
            fig_err.add_trace(go.Histogram(
                x=errors_test, name='测试集误差',
                marker_color='#e74c3c', opacity=0.7, nbinsx=20
            ))
            fig_err.update_layout(
                barmode='overlay',
                title="预测误差分布",
                xaxis_title="预测误差 (预测值 - 实际值)",
                yaxis_title="频次"
            )
            st.plotly_chart(fig_err, use_container_width=True)
        
        with col2:
            # 相对误差
            rel_errors_test = np.abs(errors_test) / (np.abs(y_test) + 1e-10) * 100
            fig_rel = px.histogram(
                x=rel_errors_test, nbins=25,
                title="测试集相对误差分布",
                labels={'x': '相对误差 (%)', 'y': '频次'},
                color_discrete_sequence=['#e74c3c']
            )
            fig_rel.add_vline(x=10, line_dash="dash", line_color="green",
                            annotation_text="10%误差线")
            fig_rel.add_vline(x=20, line_dash="dash", line_color="orange",
                            annotation_text="20%误差线")
            st.plotly_chart(fig_rel, use_container_width=True)
        
        # 统计指标
        st.markdown("#### 📊 模型评估统计")
        stat_cols = st.columns(5)
        from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
        mae_test = mean_absolute_error(y_test, y_pred_test)
        rmse_test = np.sqrt(mean_squared_error(y_test, y_pred_test))
        r2_test = r2_score(y_test, y_pred_test)
        mape_test = np.mean(np.abs(errors_test) / (np.abs(y_test) + 1e-10)) * 100
        within_10 = np.mean(rel_errors_test < 10) * 100
        
        stat_cols[0].metric("MAE", f"{mae_test:.4f}")
        stat_cols[1].metric("RMSE", f"{rmse_test:.4f}")
        stat_cols[2].metric("R²", f"{r2_test:.4f}")
        stat_cols[3].metric("MAPE", f"{mape_test:.1f}%")
        stat_cols[4].metric("10%内准确率", f"{within_10:.1f}%")
        
        # 预测vs实测详细数据表
        with st.expander("📋 查看预测vs实测详细数据"):
            pv_data = pd.DataFrame({
                '实际值': np.concatenate([y_train, y_test]),
                '预测值': np.concatenate([y_pred_train, y_pred_test]),
                '绝对误差': np.concatenate([np.abs(errors_train), np.abs(errors_test)]),
                '相对误差(%)': np.concatenate([
                    np.abs(errors_train) / (np.abs(y_train) + 1e-10) * 100,
                    rel_errors_test
                ]),
                '数据集': ['训练集'] * len(y_train) + ['测试集'] * len(y_test)
            })
            st.dataframe(pv_data.sort_values('相对误差(%)', ascending=False), 
                        use_container_width=True, height=400)

# ============================================================
# TAB 5: 材料对比
# ============================================================
with tab5:
    st.markdown(f'<div class="sub-header">⚖️ {battery_type} — 材料性能对比分析</div>', 
                unsafe_allow_html=True)
    
    st.markdown("""
    > 选择多种材料进行性能对比，**蓝色**为模型预测值，**绿色**为数据库中实际搜索值（文献统计值）
    """)
    
    if is_liquid:
        all_fillers = list(LIQUID_FILLERS.keys())
        selected_materials = st.multiselect(
            "选择填料材料进行对比（最多6种）",
            all_fillers,
            default=all_fillers[:4],
            max_selections=6,
            key="compare_materials"
        )
    else:
        all_fillers = list(SOLID_FILLERS.keys())
        selected_materials = st.multiselect(
            "选择填料材料进行对比（最多6种）",
            all_fillers,
            default=all_fillers[:4],
            max_selections=6,
            key="compare_materials"
        )
    
    if selected_materials:
        # 设定统一工况
        st.markdown("##### ⚙️ 统一工况设置")
        col1, col2, col3 = st.columns(3)
        
        if is_liquid:
            with col1:
                comp_loading = st.slider("填料负载量 (mg/cm²)", 0.1, 3.0, 1.0, 0.1, key="comp_loading")
            with col2:
                comp_temp = st.slider("温度 (°C)", 20, 60, 25, 5, key="comp_temp")
                comp_rate = st.select_slider("倍率 (C)", [0.1, 0.2, 0.5, 1.0, 2.0], 0.5, key="comp_rate")
            with col3:
                comp_cycle = st.slider("循环次数", 50, 1000, 200, 50, key="comp_cycle")
                comp_substrate = st.selectbox("基底", list(LIQUID_SUBSTRATES.keys()), key="comp_sub")
                comp_electrolyte = st.selectbox("电解液", list(LIQUID_ELECTROLYTES.keys()), key="comp_elec")
        else:
            with col1:
                comp_content = st.slider("填料含量 (wt%)", 10, 80, 40, 5, key="comp_content")
            with col2:
                comp_temp = st.slider("温度 (°C)", 20, 80, 25, 5, key="comp_temp")
                comp_rate = st.select_slider("倍率 (C)", [0.05, 0.1, 0.2, 0.5, 1.0], 0.2, key="comp_rate")
            with col3:
                comp_cycle = st.slider("循环次数", 50, 800, 200, 50, key="comp_cycle")
                comp_substrate = st.selectbox("基底/聚合物", list(SOLID_SUBSTRATES.keys()), key="comp_sub")
                comp_pressure = st.slider("压力 (MPa)", 50, 500, 200, 50, key="comp_press")
        
        # 对每种材料进行预测和统计
        compare_results = []
        
        for material in selected_materials:
            try:
                if is_liquid:
                    filler_info = LIQUID_FILLERS[material]
                    sub_info = LIQUID_SUBSTRATES[comp_substrate]
                    
                    input_feat = {
                        '填料类型': material,
                        '填料类别': filler_info['category'],
                        '填料负载量(mg/cm²)': float(comp_loading),
                        '比表面积(m²/g)': float(filler_info['sa_base']),
                        '粒径(nm)': float(filler_info['ps_base']),
                        '孔体积(cm³/g)': float(filler_info['pv_base']),
                        '基底材料': comp_substrate,
                        '隔膜厚度(μm)': float(sub_info['thickness_base']),
                        '孔隙率': float(sub_info['porosity_base']),
                        '电解液体系': comp_electrolyte,
                        '温度(°C)': comp_temp,
                        '倍率(C)': comp_rate,
                        '循环次数': comp_cycle,
                    }
                    
                    preds = predict_single(
                        liquid_results, liquid_encoders, liquid_scaler,
                        LIQUID_FEATURES, LIQUID_TARGETS, input_feat, 'liquid'
                    )
                    
                    # 从数据库中获取实际统计值
                    mat_data = liquid_df[liquid_df['填料类型'] == material]
                    
                    row = {'材料': material, '类别': filler_info['category']}
                    for target in LIQUID_TARGETS:
                        if target in preds:
                            pred_val = preds[target]['predicted_value']
                        else:
                            pred_val = np.nan
                        actual_mean = mat_data[target].mean() if len(mat_data) > 0 else np.nan
                        actual_std = mat_data[target].std() if len(mat_data) > 0 else np.nan
                        row[f'{target}_预测值'] = pred_val
                        row[f'{target}_实测均值'] = actual_mean
                        row[f'{target}_实测标准差'] = actual_std
                    compare_results.append(row)
                    
                else:
                    filler_info = SOLID_FILLERS[material]
                    sub_info = SOLID_SUBSTRATES[comp_substrate]
                    
                    input_feat = {
                        '填料类型': material,
                        '填料类别': filler_info['category'],
                        '填料含量(wt%)': float(comp_content),
                        '比表面积(m²/g)': float(filler_info['sa_base']),
                        '粒径(nm)': float(filler_info['ps_base']),
                        '基底/聚合物': comp_substrate,
                        '膜厚度(μm)': float(sub_info['thickness_base']),
                        '温度(°C)': comp_temp,
                        '压力(MPa)': float(comp_pressure),
                        '倍率(C)': comp_rate,
                        '循环次数': comp_cycle,
                    }
                    
                    preds = predict_single(
                        solid_results, solid_encoders, solid_scaler,
                        SOLID_FEATURES, SOLID_TARGETS, input_feat, 'solid'
                    )
                    
                    mat_data = solid_df[solid_df['填料类型'] == material]
                    
                    row = {'材料': material, '类别': filler_info['category']}
                    for target in SOLID_TARGETS:
                        if target in preds:
                            pred_val = preds[target]['predicted_value']
                        else:
                            pred_val = np.nan
                        actual_mean = mat_data[target].mean() if len(mat_data) > 0 else np.nan
                        actual_std = mat_data[target].std() if len(mat_data) > 0 else np.nan
                        row[f'{target}_预测值'] = pred_val
                        row[f'{target}_实测均值'] = actual_mean
                        row[f'{target}_实测标准差'] = actual_std
                    compare_results.append(row)
            except Exception as e:
                st.warning(f"材料 {material} 预测失败: {e}")
                continue
        
        # 显示对比结果
        if not compare_results:
            st.warning("未能为所选材料生成对比数据。")
            st.stop()
        
        st.markdown("#### 📊 预测值 vs 实际搜索值 对比")
        
        # 选择要对比的目标
        compare_targets = LIQUID_TARGETS if is_liquid else SOLID_TARGETS
        selected_compare_target = st.selectbox("选择对比指标", compare_targets, key="compare_target")
        
        # 柱状图对比
        materials = [r['材料'] for r in compare_results]
        pred_values = [r[f'{selected_compare_target}_预测值'] for r in compare_results]
        actual_values = [r[f'{selected_compare_target}_实测均值'] for r in compare_results]
        actual_stds = [r[f'{selected_compare_target}_实测标准差'] for r in compare_results]
        
        fig_compare = go.Figure()
        
        # 预测值（蓝色）
        fig_compare.add_trace(go.Bar(
            x=materials, y=pred_values,
            name='🔵 模型预测值',
            marker_color='#4361ee',
            text=[f'{v:.3f}' for v in pred_values],
            textposition='outside'
        ))
        
        # 实际搜索值（绿色，带误差棒）
        safe_stds = [0 if (s is None or np.isnan(s)) else s for s in actual_stds]
        fig_compare.add_trace(go.Bar(
            x=materials, y=actual_values,
            name='🟢 数据库实际搜索值(均值)',
            marker_color='#2ecc71',
            error_y=dict(type='data', array=safe_stds, visible=True),
            text=[f'{v:.3f}' if not np.isnan(v) else 'N/A' for v in actual_values],
            textposition='outside'
        ))
        
        fig_compare.update_layout(
            title=f"{selected_compare_target} — 预测值 vs 实际搜索值",
            barmode='group',
            yaxis_title=selected_compare_target,
            height=500,
            legend=dict(yanchor="top", y=0.99, xanchor="right", x=0.99)
        )
        st.plotly_chart(fig_compare, use_container_width=True)
        
        # 详细对比表
        st.markdown("#### 📋 详细对比数据表")
        
        detail_rows = []
        for r in compare_results:
            detail_row = {'材料': r['材料'], '类别': r['类别']}
            for target in compare_targets:
                pred = r[f'{target}_预测值']
                actual = r[f'{target}_实测均值']
                std = r[f'{target}_实测标准差']
                detail_row[f'{target}\n预测值'] = f"{pred:.4f}"
                if not np.isnan(actual):
                    std_str = f" ± {std:.4f}" if not np.isnan(std) else ""
                    detail_row[f'{target}\n实测值(均值±标准差)'] = f"{actual:.4f}{std_str}"
                else:
                    detail_row[f'{target}\n实测值(均值±标准差)'] = "N/A"
                if not np.isnan(actual) and abs(actual) > 1e-10:
                    diff_pct = abs(pred - actual) / abs(actual) * 100
                    detail_row[f'{target}\n偏差(%)'] = f"{diff_pct:.1f}%"
                else:
                    detail_row[f'{target}\n偏差(%)'] = "N/A"
            detail_rows.append(detail_row)
        
        detail_df = pd.DataFrame(detail_rows)
        st.dataframe(detail_df, use_container_width=True, hide_index=True)
        
        # 雷达图对比
        st.markdown("#### 🎯 多维性能雷达图")
        st.markdown("> 归一化后的多维性能对比（数值越大越好）")
        
        # 选择雷达图指标
        if is_liquid:
            radar_targets = ['初始比容量(mAh/g)', '容量保持率(%)', '库伦效率(%)', '离子电导率(mS/cm)']
            radar_labels = ['初始容量', '容量保持率', '库伦效率', '离子电导率']
            # 穿梭因子越小越好，取反
        else:
            radar_targets = ['初始比容量(mAh/g)', '容量保持率(%)', '库伦效率(%)', '电化学窗口(V)']
            radar_labels = ['初始容量', '容量保持率', '库伦效率', '电化学窗口']
        
        fig_radar = go.Figure()
        
        for r in compare_results:
            values = []
            for target in radar_targets:
                val = r.get(f'{target}_预测值', np.nan)
                if np.isnan(val):
                    values.append(0)
                    continue
                # 归一化到0-1
                col_vals = current_df[target]
                normalized = (val - col_vals.min()) / (col_vals.max() - col_vals.min() + 1e-10)
                values.append(float(np.clip(normalized, 0, 1)))
            
            values.append(values[0])  # 闭合
            labels_radar = radar_labels + [radar_labels[0]]
            
            fig_radar.add_trace(go.Scatterpolar(
                r=values, theta=labels_radar,
                fill='toself', name=r['材料'],
                opacity=0.6
            ))
        
        fig_radar.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
            title="多维性能雷达图（归一化）",
            height=500
        )
        st.plotly_chart(fig_radar, use_container_width=True)

# ============================================================
# TAB 6: 自定义材料分析
# ============================================================
with tab6:
    st.markdown(f'<div class="sub-header">🧪 {battery_type} — 自定义材料分析</div>',
                unsafe_allow_html=True)

    st.markdown("""
    > 💡 输入任意材料名称或关键词，系统将自动识别材料属性并给出完整的性能预测和分析报告。
    > 支持 **LDH、MXene、MOF、碳化物、硫化物、黑磷** 等多种新型材料。
    """)

    # ─── 搜索区域 ───
    search_query = st.text_input(
        "🔎 输入材料名称或关键词（如 LDH、MOF-808、黑磷、MXene …）",
        key="custom_search",
        placeholder="请输入材料名称，支持中英文及缩写"
    )

    if search_query:
        bt_key = 'liquid' if is_liquid else 'solid'
        ext_kb = EXTENDED_LIQUID_KB if is_liquid else EXTENDED_SOLID_KB
        train_kb = LIQUID_FILLERS if is_liquid else SOLID_FILLERS

        # 搜索扩展 KB
        ext_results = search_material(search_query, bt_key)
        # 搜索训练 KB
        train_results = search_training_kb(search_query, train_kb)

        # 合并结果（扩展库优先）
        seen_keys = set()
        merged_results = []
        for key, info in ext_results:
            if key not in seen_keys:
                merged_results.append((key, info, True))  # True = 扩展库
                seen_keys.add(key)
        for key, info in train_results:
            if key not in seen_keys:
                merged_results.append((key, info, False))  # False = 训练库
                seen_keys.add(key)

        if not merged_results:
            st.warning(
                f"未找到与 **{search_query}** 相关的材料。请尝试：\n"
                "- 英文名称（如 LDH、MOF、MXene、BP）\n"
                "- 中文名称（如 黑磷、碳化钨、氧化锆）\n"
                "- 类别关键词（如 碳基、氧化物、硫化物）"
            )
        else:
            st.success(f"找到 **{len(merged_results)}** 个相关材料：")

            # 构建选择项
            option_labels = []
            option_keys = []
            option_is_ext = []
            for key, info, is_ext in merged_results:
                if is_ext:
                    label = f"✅ {key}（{info['name_zh']}）— 扩展材料库"
                else:
                    label = f"📋 {key}（{info['category']}）— 训练数据库"
                option_labels.append(label)
                option_keys.append(key)
                option_is_ext.append(is_ext)

            selected_idx = 0
            if len(option_labels) > 1:
                selected_label = st.radio("选择材料", option_labels,
                                          key="custom_mat_select")
                selected_idx = option_labels.index(selected_label)
            else:
                st.markdown(f"**自动选择**: {option_labels[0]}")

            sel_key = option_keys[selected_idx]
            sel_is_ext = option_is_ext[selected_idx]
            sel_info = ext_kb[sel_key] if sel_is_ext else train_kb[sel_key]

            st.markdown("---")

            # ─── 材料信息卡片 ───
            if sel_is_ext:
                info_c1, info_c2, info_c3 = st.columns([1.2, 1, 0.8])
                with info_c1:
                    st.markdown(f"### 📌 {sel_key}")
                    st.markdown(f"**中文名**: {sel_info['name_zh']}")
                    st.markdown(f"**类别**: {sel_info['category']}")
                    st.markdown(f"**代理材料**: `{sel_info['proxy_material']}`"
                                f"（用于模型编码）")
                    st.markdown(f"**文献**: {sel_info['literature_ref']}")
                    st.caption(sel_info['description'])

                with info_c2:
                    st.markdown("##### 💪 优势")
                    for adv in sel_info.get('advantages', []):
                        st.markdown(f"- ✅ {adv}")
                    st.markdown("##### ⚠️ 劣势")
                    for dis in sel_info.get('disadvantages', []):
                        st.markdown(f"- ❌ {dis}")

                with info_c3:
                    affinity_val = sel_info.get('affinity')
                    if affinity_val is not None:
                        pct = affinity_val * 100
                        clr = ('#2ecc71' if pct > 80 else
                               '#f39c12' if pct > 60 else '#e74c3c')
                        st.markdown(f"""
                        <div style="text-align:center; padding:1rem;
                                    background:#f8f9fa; border-radius:10px;
                                    margin-top:0.5rem;">
                            <div style="font-size:0.85rem; color:#666;">
                                多硫化物亲和力</div>
                            <div style="font-size:2.5rem; font-weight:700;
                                        color:{clr};">{pct:.0f}%</div>
                            <div style="width:80%; margin:0.5rem auto;
                                        background:#eee; border-radius:5px;
                                        height:10px;">
                                <div style="width:{pct}%; background:{clr};
                                            border-radius:5px;
                                            height:10px;"></div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                    # 固态材料显示离子电导率
                    cond_val = sel_info.get('cond_base')
                    if cond_val is not None:
                        st.markdown(f"""
                        <div style="text-align:center; padding:1rem;
                                    background:#f0f4ff; border-radius:10px;
                                    margin-top:0.5rem;">
                            <div style="font-size:0.85rem; color:#666;">
                                参考离子电导率</div>
                            <div style="font-size:1.6rem; font-weight:700;
                                        color:#3498db;">
                                {cond_val:.2e} S/cm</div>
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.markdown(f"### 📌 {sel_key}（训练数据库材料）")
                st.markdown(f"**类别**: {sel_info['category']}")
                st.info("ℹ️ 此材料已在训练数据库中，也可使用 Tab 3「性能预测」"
                        "获得更直接的结果。下方仍可调整参数进行预测。")

            # ─── 属性调整 + 电池配置 ───
            st.markdown("#### ⚙️ 材料属性与电池配置")
            prop_col, config_col = st.columns(2)

            with prop_col:
                st.markdown("##### 📐 物理属性（可调整滑块微调）")
                _sa_default = float(sel_info.get('sa_base', 100))
                cust_sa = st.slider("比表面积 (m²/g)", 5.0, 3500.0,
                                    _sa_default, 5.0, key="cust_sa")
                _ps_default = float(sel_info.get('ps_base', 30) or 30)
                cust_ps = st.slider("粒径 (nm)", 1.0, 1000.0,
                                    _ps_default, 1.0, key="cust_ps")
                if is_liquid:
                    _pv_default = float(sel_info.get('pv_base', 0.2) or 0.2)
                    cust_pv = st.slider("孔体积 (cm³/g)", 0.01, 2.0,
                                        _pv_default, 0.01, key="cust_pv")
                    cust_loading = st.slider(
                        "填料负载量 (mg/cm²)", 0.05, 3.0, 1.0, 0.05,
                        key="cust_loading")
                else:
                    cust_content = st.slider(
                        "填料含量 (wt%)", 10.0, 80.0, 40.0, 1.0,
                        key="cust_content")

            with config_col:
                st.markdown("##### 🔧 电池配置")
                if is_liquid:
                    cust_sub = st.selectbox(
                        "基底材料", list(LIQUID_SUBSTRATES.keys()),
                        key="cust_sub")
                    _sub = LIQUID_SUBSTRATES[cust_sub]
                    cust_thick = st.slider(
                        "隔膜厚度 (μm)", 5.0, 700.0,
                        float(_sub['thickness_base']), 1.0,
                        key="cust_thick")
                    cust_por = st.slider(
                        "孔隙率", 0.15, 0.95,
                        float(_sub['porosity_base']), 0.01,
                        key="cust_por")
                    cust_elec = st.selectbox(
                        "电解液体系", list(LIQUID_ELECTROLYTES.keys()),
                        key="cust_elec")
                    cust_temp = st.slider(
                        "温度 (°C)", 20, 80, 25, 1, key="cust_temp")
                    cust_rate = st.select_slider(
                        "倍率 (C)",
                        [0.1, 0.2, 0.5, 1.0, 2.0, 3.0, 5.0], 0.5,
                        key="cust_rate")
                    cust_cycle = st.slider(
                        "循环次数", 50, 1000, 200, 50, key="cust_cycle")
                else:
                    cust_sub = st.selectbox(
                        "基底/聚合物", list(SOLID_SUBSTRATES.keys()),
                        key="cust_sub")
                    _sub = SOLID_SUBSTRATES[cust_sub]
                    cust_thick = st.slider(
                        "膜厚度 (μm)", 10.0, 200.0,
                        float(_sub['thickness_base']), 1.0,
                        key="cust_thick")
                    cust_temp = st.slider(
                        "温度 (°C)", 20, 100, 25, 1, key="cust_temp")
                    cust_press = st.slider(
                        "压力 (MPa)", 50.0, 500.0, 200.0, 10.0,
                        key="cust_press")
                    cust_rate = st.select_slider(
                        "倍率 (C)", [0.05, 0.1, 0.2, 0.5, 1.0], 0.2,
                        key="cust_rate")
                    cust_cycle = st.slider(
                        "循环次数", 50, 800, 200, 50, key="cust_cycle")

            # ─── 预测按钮 ───
            if st.button("🔮 运行性能预测", key="cust_predict_btn",
                         type="primary", use_container_width=True):
                try:
                    # 确定编码用的材料名和类别
                    if sel_is_ext:
                        proxy_name = sel_info['proxy_material']
                        proxy_cat = sel_info['category']
                    else:
                        proxy_name = sel_key
                        proxy_cat = sel_info['category']

                    # 构建特征字典
                    if is_liquid:
                        cust_input = {
                            '填料类型': proxy_name,
                            '填料类别': proxy_cat,
                            '填料负载量(mg/cm²)': cust_loading,
                            '比表面积(m²/g)': cust_sa,
                            '粒径(nm)': cust_ps,
                            '孔体积(cm³/g)': cust_pv,
                            '基底材料': cust_sub,
                            '隔膜厚度(μm)': cust_thick,
                            '孔隙率': cust_por,
                            '电解液体系': cust_elec,
                            '温度(°C)': cust_temp,
                            '倍率(C)': cust_rate,
                            '循环次数': cust_cycle,
                        }
                        cust_preds = predict_single(
                            liquid_results, liquid_encoders, liquid_scaler,
                            LIQUID_FEATURES, LIQUID_TARGETS,
                            cust_input, 'liquid')
                    else:
                        cust_input = {
                            '填料类型': proxy_name,
                            '填料类别': proxy_cat,
                            '填料含量(wt%)': cust_content,
                            '比表面积(m²/g)': cust_sa,
                            '粒径(nm)': cust_ps,
                            '基底/聚合物': cust_sub,
                            '膜厚度(μm)': cust_thick,
                            '温度(°C)': cust_temp,
                            '压力(MPa)': cust_press,
                            '倍率(C)': cust_rate,
                            '循环次数': cust_cycle,
                        }
                        cust_preds = predict_single(
                            solid_results, solid_encoders, solid_scaler,
                            SOLID_FEATURES, SOLID_TARGETS,
                            cust_input, 'solid')

                    if not cust_preds:
                        st.warning("未能生成预测结果，请检查参数配置。")
                        st.stop()

                    # ─── 显示预测结果 ───
                    st.markdown("---")
                    st.markdown("#### 📊 预测结果")
                    if sel_is_ext:
                        st.caption(
                            f"⚡ 使用代理材料 **{proxy_name}** 的分类编码 +"
                            f" **{sel_key}** 的实际物理属性进行预测")

                    n_p = len(cust_preds)
                    pcols = st.columns(n_p)
                    for idx, (tgt, pi) in enumerate(cust_preds.items()):
                        with pcols[idx]:
                            v = pi['predicted_value']
                            u = pi['uncertainty']
                            r2 = pi['r2']
                            if '电导率' in tgt:
                                vs, us = f"{v:.4f}", f"±{u:.4f}"
                            elif '容量' in tgt or '阻抗' in tgt:
                                vs, us = f"{v:.1f}", f"±{u:.1f}"
                            elif ('效率' in tgt or '保持率' in tgt
                                  or '窗口' in tgt):
                                vs, us = f"{v:.2f}", f"±{u:.2f}"
                            else:
                                vs, us = f"{v:.4f}", f"±{u:.4f}"
                            rc = ("🟢" if r2 > 0.8 else
                                  "🟡" if r2 > 0.5 else "🔴")
                            st.markdown(f"""
                            <div style="background:linear-gradient(
                                135deg,#2c3e50 0%,#3498db 100%);
                                padding:12px; border-radius:10px;
                                color:white; text-align:center;">
                              <div style="font-size:0.78rem;
                                opacity:0.9;">{tgt}</div>
                              <div style="font-size:1.6rem;
                                font-weight:700;margin:4px 0;">
                                {vs}</div>
                              <div style="font-size:0.72rem;
                                opacity:0.8;">{us}</div>
                              <div style="font-size:0.68rem;
                                margin-top:4px;">{rc} R²={r2:.3f}
                              </div>
                            </div>""", unsafe_allow_html=True)

                    # ─── 同类别对比雷达图 ───
                    st.markdown("#### 🎯 同类别材料性能对比")
                    cat_mask = current_df['填料类别'] == proxy_cat
                    cat_data = current_df[cat_mask]

                    if is_liquid:
                        radar_tgts = ['初始比容量(mAh/g)',
                                      '容量保持率(%)',
                                      '库伦效率(%)']
                        radar_lbls = ['初始容量', '容量保持率', '库伦效率']
                    else:
                        radar_tgts = ['初始比容量(mAh/g)',
                                      '容量保持率(%)',
                                      '库伦效率(%)',
                                      '电化学窗口(V)']
                        radar_lbls = ['初始容量', '容量保持率',
                                      '库伦效率', '电化学窗口']

                    def _norm(val, col_name):
                        """归一化到 [0,1]"""
                        cvals = current_df[col_name]
                        return float(np.clip(
                            (val - cvals.min()) /
                            (cvals.max() - cvals.min() + 1e-10), 0, 1))

                    # 自定义材料预测值
                    cust_r = [_norm(cust_preds[t]['predicted_value'], t)
                              if t in cust_preds else 0
                              for t in radar_tgts]
                    cust_r.append(cust_r[0])

                    # 同类别平均
                    if len(cat_data) > 0:
                        cat_r = [_norm(cat_data[t].mean(), t)
                                 for t in radar_tgts]
                    else:
                        cat_r = [0.5] * len(radar_tgts)
                    cat_r.append(cat_r[0])

                    # 全体平均
                    all_r = [_norm(current_df[t].mean(), t)
                             for t in radar_tgts]
                    all_r.append(all_r[0])

                    theta = radar_lbls + [radar_lbls[0]]

                    fig_cust_radar = go.Figure()
                    fig_cust_radar.add_trace(go.Scatterpolar(
                        r=cust_r, theta=theta, fill='toself',
                        name=f'{sel_key}（预测）',
                        opacity=0.7,
                        line=dict(color='#e74c3c', width=3)))
                    fig_cust_radar.add_trace(go.Scatterpolar(
                        r=cat_r, theta=theta, fill='toself',
                        name=f'{proxy_cat} 类平均',
                        opacity=0.4,
                        line=dict(color='#3498db', width=2)))
                    fig_cust_radar.add_trace(go.Scatterpolar(
                        r=all_r, theta=theta, fill='toself',
                        name='全体材料平均',
                        opacity=0.3,
                        line=dict(color='#95a5a6', width=1,
                                  dash='dash')))
                    fig_cust_radar.update_layout(
                        polar=dict(radialaxis=dict(
                            visible=True, range=[0, 1])),
                        title=(f"性能雷达图：{sel_key} vs "
                               f"{proxy_cat}类平均 vs 全体平均"),
                        height=480,
                        legend=dict(orientation="h",
                                    yanchor="bottom", y=-0.18,
                                    xanchor="center", x=0.5))
                    st.plotly_chart(fig_cust_radar,
                                   use_container_width=True)

                    # ─── 性能排名定位 ───
                    st.markdown("#### 📈 性能排名定位")
                    rank_rows = []
                    for tgt, pi in cust_preds.items():
                        v = pi['predicted_value']
                        cvals = current_df[tgt].values
                        # 阻抗 / 穿梭因子：越低越好
                        if '穿梭' in tgt or '阻抗' in tgt:
                            pctl = (cvals > v).mean() * 100
                        else:
                            pctl = (cvals < v).mean() * 100
                        if '电导率' in tgt or '穿梭' in tgt:
                            vf = f"{v:.4f}"
                        else:
                            vf = f"{v:.2f}"
                        stars = ('⭐⭐⭐' if pctl > 75
                                 else '⭐⭐' if pctl > 50 else '⭐')
                        rank_rows.append({
                            '性能指标': tgt,
                            '预测值': vf,
                            '超越数据库样本(%)': f"{pctl:.1f}%",
                            '评级': stars,
                        })
                    st.dataframe(pd.DataFrame(rank_rows),
                                 use_container_width=True,
                                 hide_index=True)

                    # ─── 排名柱状图 ───
                    fig_rank = go.Figure()
                    tgt_names = [r['性能指标'] for r in rank_rows]
                    pctl_vals = [float(r['超越数据库样本(%)']
                                       .replace('%', ''))
                                 for r in rank_rows]
                    colors = ['#2ecc71' if p > 75
                              else '#f39c12' if p > 50
                              else '#e74c3c' for p in pctl_vals]
                    fig_rank.add_trace(go.Bar(
                        x=tgt_names, y=pctl_vals,
                        marker_color=colors,
                        text=[f'{p:.1f}%' for p in pctl_vals],
                        textposition='outside'))
                    fig_rank.update_layout(
                        title=f'{sel_key} 各指标排名百分位',
                        yaxis_title='超越数据库样本 (%)',
                        yaxis_range=[0, 105], height=380)
                    st.plotly_chart(fig_rank,
                                   use_container_width=True)

                    # ─── 推荐方案报告 ───
                    if sel_is_ext:
                        st.markdown("#### 📋 材料推荐报告")
                        rpt1, rpt2 = st.columns(2)

                        with rpt1:
                            st.markdown(
                                f"##### 📌 {sel_key}"
                                f"（{sel_info['name_zh']}）")
                            st.markdown(
                                f"**材料描述**: {sel_info['description']}")
                            st.markdown(
                                f"**文献参考**: "
                                f"{sel_info['literature_ref']}")
                            st.markdown("**优势**:")
                            for a in sel_info.get('advantages', []):
                                st.markdown(f"  - ✅ {a}")
                            st.markdown("**劣势**:")
                            for d in sel_info.get('disadvantages', []):
                                st.markdown(f"  - ⚠️ {d}")

                        with rpt2:
                            st.markdown("##### 🔧 推荐实验方案")
                            rec = get_recommended_config(
                                sel_info, bt_key)
                            for k, val in rec.items():
                                st.markdown(f"**{k}**: {val}")

                            st.markdown("##### 📊 预期性能范围")
                            for tgt, pi in cust_preds.items():
                                pv = pi['predicted_value']
                                pu = pi['uncertainty']
                                lo = max(0, pv - pu)
                                hi = pv + pu
                                if '电导率' in tgt:
                                    st.markdown(
                                        f"- {tgt}: "
                                        f"{lo:.4f} ~ {hi:.4f}")
                                else:
                                    st.markdown(
                                        f"- {tgt}: "
                                        f"{lo:.2f} ~ {hi:.2f}")

                except Exception as exc:
                    st.error(f"预测过程中出错: {exc}")
                    import traceback
                    with st.expander("查看详细错误信息"):
                        st.code(traceback.format_exc())

    else:
        # 未输入时展示知识库概览
        st.markdown("---")
        st.markdown("#### 📚 扩展材料知识库概览")
        if is_liquid:
            kb_for_overview = EXTENDED_LIQUID_KB
            st.markdown(f"当前模式: **液态锂硫电池** | "
                        f"扩展材料库包含 **{len(kb_for_overview)}** 种材料")
        else:
            kb_for_overview = EXTENDED_SOLID_KB
            st.markdown(f"当前模式: **固态锂硫电池** | "
                        f"扩展材料库包含 **{len(kb_for_overview)}** 种材料")

        overview_rows = []
        for k, v in kb_for_overview.items():
            row = {
                '材料名称': k,
                '中文名': v.get('name_zh', ''),
                '类别': v.get('category', ''),
                '代理材料': v.get('proxy_material', ''),
                '比表面积(m²/g)': v.get('sa_base', ''),
            }
            if is_liquid:
                row['亲和力'] = v.get('affinity', '')
            else:
                cond = v.get('cond_base')
                row['参考电导率(S/cm)'] = (f"{cond:.2e}" if cond
                                            else '')
            overview_rows.append(row)

        st.dataframe(pd.DataFrame(overview_rows),
                     use_container_width=True, hide_index=True,
                     height=min(400, 36 * len(overview_rows) + 38))

        st.info("👆 在上方搜索框输入材料名称即可开始分析。"
                "支持精确匹配、模糊匹配和别名匹配。")


# ============================================================
# 页脚
# ============================================================
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #888; font-size: 0.85rem;">
    🔋 锂硫电池隔膜填料与适配基底材料设计平台 | 
    数据基于文献物理关系编码生成 (1250+样本) | 
    模型: Random Forest / Gradient Boosting / Ridge Regression | 
    可解释性优先
</div>
""", unsafe_allow_html=True)
