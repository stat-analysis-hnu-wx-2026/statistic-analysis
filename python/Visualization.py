import pandas as pd
import matplotlib.pyplot as plt
import io

def generate_visualization(options):
    # 1. 兼容 Pyodide 的 JsProxy 转换
    if not isinstance(options, dict):
        to_py = getattr(options, "to_py", None)
        if callable(to_py):
            options = to_py()
        else:
            options = dict(options)
            
    # 2. 通过 options.get 读取数据路径
    data_path = options.get('data_path')
    if not data_path:
        return {"error": "请先在左侧上传数据文件"}
    
    chart_type = options.get('chart_type', '散点图')
    x_var = options.get('x_var')
    y_var = options.get('y_var')
    
    try:
        df = pd.read_csv(data_path)
        
        data_volume = len(df)
        dimensions = df.shape[1]
        missing_values = int(df.isna().sum().sum())
        
        numeric_df = df.select_dtypes(include='number')
        desc_table = []
        for col in numeric_df.columns:
            mean_val = numeric_df[col].mean()
            std_val = numeric_df[col].std()
            desc_table.append([
                str(col), 
                f"{mean_val:.4f}" if pd.notna(mean_val) else "-", 
                f"{std_val:.4f}" if pd.notna(std_val) else "-"
            ])
        
        # 3. 纯 Matplotlib 生成 SVG 字符串
        fig, ax = plt.subplots(figsize=(10, 5))
        
        if chart_type == '散点图' and x_var in df.columns and y_var in df.columns:
            ax.scatter(df[x_var], df[y_var], alpha=0.7)
            ax.set_xlabel(x_var)
            ax.set_ylabel(y_var)
        elif chart_type == '折线图' and x_var in df.columns and y_var in df.columns:
            ax.plot(df[x_var], df[y_var], marker='o')
            ax.set_xlabel(x_var)
            ax.set_ylabel(y_var)
        elif chart_type == '箱线图' and y_var in df.columns:
            if x_var and x_var in df.columns:
                groups = df.groupby(x_var)[y_var].apply(list)
                ax.boxplot(groups.values, labels=groups.keys())
                ax.set_xlabel(x_var)
            else:
                ax.boxplot(df[y_var].dropna())
            ax.set_ylabel(y_var)
        elif chart_type == '热力图':
            corr = numeric_df.corr()
            cax = ax.matshow(corr, cmap='Blues', aspect='auto')
            fig.colorbar(cax)
            ax.set_xticks(range(len(corr.columns)))
            ax.set_yticks(range(len(corr.columns)))
            ax.set_xticklabels(corr.columns, rotation=45)
            ax.set_yticklabels(corr.columns)
        else:
            ax.text(0.5, 0.5, '图表参数不足或列名不存在\n请检查 X轴/Y轴 变量是否填写正确', 
                    ha='center', va='center', fontsize=12, color='gray')

        ax.set_title(chart_type)
        fig.tight_layout()
        
        buf = io.BytesIO()
        fig.savefig(buf, format='svg')
        plt.close(fig) # 释放 WASM 内存
        svg_str = buf.getvalue().decode('utf-8')
        
        # 4. 返回对应格式的字典
        return {
            "svgs": [svg_str],
            "metrics": {
                "数据量": data_volume,
                "维度": dimensions,
                "缺失值": missing_values
            },
            "tables": [
                {
                    "header": ["特征", "均值", "标准差"],
                    "rows": desc_table if desc_table else [["-", "-", "-"]]
                }
            ]
        }
        
    except Exception as e:
        return {"error": str(e)}