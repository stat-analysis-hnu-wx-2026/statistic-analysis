import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from io import BytesIO

def _read_data(data_path):
    return pd.read_csv(data_path)

def generate_visualization(options):
    data_path = options.get('data_path')
    if not data_path:
        return {"error": "请先上传数据文件"}
    
    chart_type = options.get('chart_type', '散点图')
    x_var = options.get('x_var')
    y_var = options.get('y_var')
    
    try:
        df = _read_data(data_path)
        
        data_volume = len(df)
        dimensions = df.shape[1]
        missing_values = df.isna().sum().sum()
        
        numeric_df = df.select_dtypes(include='number')
        desc_table = []
        for col in numeric_df.columns:
            mean_val = numeric_df[col].mean()
            std_val = numeric_df[col].std()
            desc_table.append([
                col, 
                round(mean_val, 4) if pd.notna(mean_val) else "-", 
                round(std_val, 4) if pd.notna(std_val) else "-"
            ])
        
        fig, ax = plt.subplots(figsize=(10, 5))
        
        if chart_type == '散点图' and x_var in df.columns and y_var in df.columns:
            sns.scatterplot(data=df, x=x_var, y=y_var, ax=ax)
        elif chart_type == '折线图' and x_var in df.columns and y_var in df.columns:
            sns.lineplot(data=df, x=x_var, y=y_var, ax=ax)
        elif chart_type == '箱线图' and y_var in df.columns:
            if x_var and x_var in df.columns:
                sns.boxplot(data=df, x=x_var, y=y_var, ax=ax)
            else:
                sns.boxplot(data=df, y=y_var, ax=ax)
        elif chart_type == '热力图':
            sns.heatmap(numeric_df.corr(), annot=True, cmap='Blues', ax=ax)
        else:
            ax.text(0.5, 0.5, '参数不足或变量不存在', ha='center', va='center')

        ax.set_title(chart_type)
        
        buf = BytesIO()
        fig.tight_layout()
        fig.savefig(buf, format='svg')
        plt.close(fig)
        
        return {
            "metrics": {
                "数据量": str(data_volume),
                "维度": str(dimensions),
                "缺失值": str(missing_values)
            },
            "tables": [
                {
                    "header": ["特征", "均值", "标准差"],
                    "rows": desc_table
                }
            ],
            "svg": buf.getvalue().decode('utf-8')
        }
        
    except Exception as e:
        return {"error": str(e)}