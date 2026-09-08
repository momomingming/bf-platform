"""
锂硫电池材料预测模型构建模块
以可解释性优先，使用Random Forest / Gradient Boosting / Linear Regression
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.tree import DecisionTreeRegressor
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import LabelEncoder, StandardScaler
import warnings
warnings.filterwarnings('ignore')

try:
    from xgboost import XGBRegressor
    HAS_XGB = True
except ImportError:
    HAS_XGB = False


# 液态电池特征和目标
LIQUID_FEATURES = [
    '填料类型', '填料类别', '填料负载量(mg/cm²)', '比表面积(m²/g)', 
    '粒径(nm)', '孔体积(cm³/g)', '基底材料', '隔膜厚度(μm)',
    '孔隙率', '电解液体系', '温度(°C)', '倍率(C)', '循环次数'
]

LIQUID_TARGETS = [
    '离子电导率(mS/cm)', '初始比容量(mAh/g)', '容量保持率(%)', 
    '库伦效率(%)', '穿梭因子'
]

# 固态电池特征和目标
SOLID_FEATURES = [
    '填料类型', '填料类别', '填料含量(wt%)', '比表面积(m²/g)',
    '粒径(nm)', '基底/聚合物', '膜厚度(μm)', '温度(°C)',
    '压力(MPa)', '倍率(C)', '循环次数'
]

SOLID_TARGETS = [
    '离子电导率(mS/cm)', '界面阻抗(Ω·cm²)', '初始比容量(mAh/g)',
    '容量保持率(%)', '库伦效率(%)', '电化学窗口(V)'
]


def encode_categoricals(df, feature_cols, label_encoders=None):
    """对分类变量进行Label Encoding"""
    df_encoded = df.copy()
    if label_encoders is None:
        label_encoders = {}
        for col in feature_cols:
            if df[col].dtype == 'object':
                le = LabelEncoder()
                df_encoded[col] = le.fit_transform(df[col])
                label_encoders[col] = le
            else:
                df_encoded[col] = df[col].values
    else:
        for col in feature_cols:
            if col in label_encoders:
                # Handle unseen labels
                le = label_encoders[col]
                known = set(le.classes_)
                df_encoded[col] = df[col].map(
                    lambda x: le.transform([x])[0] if x in known else -1
                )
            else:
                df_encoded[col] = df[col].values
    return df_encoded, label_encoders


def train_models(df, feature_cols, target_cols, test_size=0.2, random_state=42):
    """
    训练多个可解释模型，返回模型字典、评估指标和特征重要性
    
    Parameters:
    -----------
    df : DataFrame - 数据
    feature_cols : list - 特征列名
    target_cols : list - 目标列名
    test_size : float - 测试集比例
    
    Returns:
    --------
    results : dict - 每个目标的模型结果
    """
    # 编码分类变量
    df_enc, label_encoders = encode_categoricals(df, feature_cols)
    
    X = df_enc[feature_cols].values.astype(float)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # 划分训练集/测试集
    X_train, X_test, X_train_s, X_test_s, train_idx, test_idx = train_test_split(
        X, X_scaled, np.arange(len(X)), test_size=test_size, random_state=random_state
    )
    
    results = {}
    
    for target in target_cols:
        y = df_enc[target].values.astype(float)
        
        # 对离子电导率取log以改善分布
        use_log = (target == '离子电导率(mS/cm)')
        y_train = np.log10(y[train_idx]) if use_log else y[train_idx]
        y_test = np.log10(y[test_idx]) if use_log else y[test_idx]
        
        # 定义模型
        models = {
            'Random Forest': RandomForestRegressor(
                n_estimators=200, max_depth=12, min_samples_split=5,
                min_samples_leaf=3, random_state=random_state, n_jobs=-1
            ),
            'Gradient Boosting': GradientBoostingRegressor(
                n_estimators=200, max_depth=5, learning_rate=0.1,
                min_samples_split=5, min_samples_leaf=3, random_state=random_state
            ),
            'Ridge Regression': Ridge(alpha=1.0),
        }
        
        if HAS_XGB:
            models['XGBoost'] = XGBRegressor(
                n_estimators=200, max_depth=6, learning_rate=0.1,
                min_child_weight=3, random_state=random_state, verbosity=0
            )
        
        target_results = {}
        best_r2 = -999
        best_model_name = None
        
        for model_name, model in models.items():
            # 线性模型使用标准化数据
            if model_name == 'Ridge Regression':
                model.fit(X_train_s, y_train)
                y_pred_train = model.predict(X_train_s)
                y_pred_test = model.predict(X_test_s)
            else:
                model.fit(X_train, y_train)
                y_pred_train = model.predict(X_train)
                y_pred_test = model.predict(X_test)
            
            # 反变换
            if use_log:
                y_pred_train_real = 10**y_pred_train
                y_pred_test_real = 10**y_pred_test
                y_train_real = 10**y_train
                y_test_real = 10**y_test
            else:
                y_pred_train_real = y_pred_train
                y_pred_test_real = y_pred_test
                y_train_real = y_train
                y_test_real = y_test
            
            # 评估指标
            mae = mean_absolute_error(y_test_real, y_pred_test_real)
            rmse = np.sqrt(mean_squared_error(y_test_real, y_pred_test_real))
            r2 = r2_score(y_test_real, y_pred_test_real)
            
            # 交叉验证
            if model_name != 'Ridge Regression':
                cv_scores = cross_val_score(model, X_train, y_train, cv=5, scoring='r2')
            else:
                cv_scores = cross_val_score(model, X_train_s, y_train, cv=5, scoring='r2')
            
            # 特征重要性
            if hasattr(model, 'feature_importances_'):
                importances = model.feature_importances_
            elif hasattr(model, 'coef_'):
                importances = np.abs(model.coef_)
                importances = importances / importances.sum()
            else:
                importances = np.zeros(len(feature_cols))
            
            target_results[model_name] = {
                'model': model,
                'mae': mae,
                'rmse': rmse,
                'r2': r2,
                'cv_r2_mean': cv_scores.mean(),
                'cv_r2_std': cv_scores.std(),
                'feature_importances': dict(zip(feature_cols, importances)),
                'y_train': y_train_real,
                'y_test': y_test_real,
                'y_pred_train': y_pred_train_real,
                'y_pred_test': y_pred_test_real,
                'train_idx': train_idx,
                'test_idx': test_idx,
            }
            
            if r2 > best_r2:
                best_r2 = r2
                best_model_name = model_name
        
        target_results['best_model'] = best_model_name
        results[target] = target_results
    
    return results, label_encoders, scaler


def predict_single(models_dict, label_encoders, scaler, feature_cols, target_cols, 
                   input_features, battery_type='liquid'):
    """
    对单个输入进行预测
    
    Parameters:
    -----------
    models_dict : dict - 训练好的模型
    label_encoders : dict - 编码器
    input_features : dict - 输入特征值
    battery_type : str - 'liquid' or 'solid'
    
    Returns:
    --------
    predictions : dict - 每个目标的预测值和置信区间
    """
    # 构建特征向量
    X_input = []
    for col in feature_cols:
        val = input_features.get(col, 0)
        if col in label_encoders:
            le = label_encoders[col]
            if val in le.classes_:
                X_input.append(le.transform([val])[0])
            else:
                X_input.append(-1)
        else:
            X_input.append(float(val))
    
    X_input = np.array(X_input).reshape(1, -1)
    X_input_scaled = scaler.transform(X_input)
    
    predictions = {}
    for target in target_cols:
        if target not in models_dict:
            continue
        target_models = models_dict[target]
        best_name = target_models['best_model']
        best_result = target_models[best_name]
        model = best_result['model']
        
        use_log = (target == '离子电导率(mS/cm)')
        
        if best_name == 'Ridge Regression':
            pred = model.predict(X_input_scaled)[0]
        else:
            pred = model.predict(X_input)[0]
        
        if use_log:
            pred = 10**pred
        
        # 使用多个模型预测的方差作为不确定性估计
        all_preds = []
        for model_name, model_result in target_models.items():
            if model_name == 'best_model':
                continue
            m = model_result['model']
            if model_name == 'Ridge Regression':
                p = m.predict(X_input_scaled)[0]
            else:
                p = m.predict(X_input)[0]
            if use_log:
                p = 10**p
            all_preds.append(p)
        
        pred_std = np.std(all_preds) if all_preds else pred * 0.05
        
        predictions[target] = {
            'predicted_value': pred,
            'uncertainty': pred_std,
            'best_model': best_name,
            'r2': best_result['r2'],
            'all_model_predictions': {name: (10**model_result['model'].predict(X_input_scaled if name == 'Ridge Regression' else X_input)[0]) if use_log else model_result['model'].predict(X_input_scaled if name == 'Ridge Regression' else X_input)[0] for name, model_result in target_models.items() if name != 'best_model'}
        }
    
    return predictions


def get_feature_importance_summary(results, feature_cols):
    """获取所有目标的特征重要性汇总"""
    importance_df = pd.DataFrame(index=feature_cols)
    for target, target_results in results.items():
        best_name = target_results['best_model']
        importances = target_results[best_name]['feature_importances']
        importance_df[target] = [importances.get(f, 0) for f in feature_cols]
    importance_df['平均重要性'] = importance_df.mean(axis=1)
    importance_df = importance_df.sort_values('平均重要性', ascending=False)
    return importance_df
