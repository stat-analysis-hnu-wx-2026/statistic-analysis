import pandas as pd
import matplotlib.pyplot as plt
import io

def generate_visualization(options):
    if not isinstance(options, dict):
        to_py = getattr(options, "to_py", None)
        if callable(to_py):
            options = to_py()
        else:
            options = dict(options)
            
    data_path = options.get('data_path')
    if not data_path:
        return {"error": "请先在左侧上传数据文件"}
    
    chart_type = options.get('chart_type', '单变量条图')
    x_var = options.get('x_var')
    y_var = options.get('y_var')
    
    try:
        if str(data_path).endswith('.csv'):
            df = pd.read_csv(data_path)
        else:
            df = pd.read_excel(data_path)
            
        if df.select_dtypes(include=['object']).shape[1] > 0:
            first_obj_col = df.select_dtypes(include=['object']).columns[0]
            df.set_index(first_obj_col, inplace=True)
            
        data_volume = len(df)
        dimensions = df.shape[1]
        missing_values = int(df.isna().sum().sum())
        
        numeric_df = df.select_dtypes(include='number')
        
        mean_series = numeric_df.mean()
        mean_table = [["变量", "均值"]] + [[str(k), f"{v:.4f}"] for k, v in mean_series.items()]
        
        cov_df = numeric_df.cov()
        cov_table = [["变量"] + list(cov_df.columns)]
        for idx, row in cov_df.iterrows():
            cov_table.append([str(idx)] + [f"{x:.4f}" for x in row])
            
        corr_df = numeric_df.corr()
        corr_table = [["变量"] + list(corr_df.columns)]
        for idx, row in corr_df.iterrows():
            corr_table.append([str(idx)] + [f"{x:.4f}" for x in row])

        plt.rcParams['font.sans-serif'] = ['SimHei']
        plt.rcParams['axes.unicode_minus'] = False
        
        if chart_type == '多变量矩阵散点图':
            axes = pd.plotting.scatter_matrix(numeric_df, figsize=(10, 10))
            fig = axes[0, 0].get_figure()
        else:
            fig, ax = plt.subplots(figsize=(10, 5))
            if chart_type == '单变量条图' and y_var in df.columns:
                df[y_var].plot(kind='bar', ax=ax)
            elif chart_type == '多变量条图':
                numeric_df.plot(kind='bar', ax=ax)
            elif chart_type == '基于单样品的条图' and x_var in df.index:
                df.loc[[x_var]].plot(kind='bar', ax=ax)
            elif chart_type == '统计量的箱线图':
                numeric_df.plot(kind='box', ax=ax)
            elif chart_type == '两变量散点图' and x_var in df.columns and y_var in df.columns:
                df.plot(kind='scatter', x=x_var, y=y_var, ax=ax)
            else:
                ax.text(0.5, 0.5, '参数不足或变量不存在', ha='center', va='center', fontsize=12)
            fig.tight_layout()
            
        buf = io.BytesIO()
        fig.savefig(buf, format='svg')
        plt.close(fig)
        svg_str = buf.getvalue().decode('utf-8')
        
        return {
            "svgs": [svg_str],
            "metrics": {
                "数据量": data_volume,
                "维度": dimensions,
                "缺失值": missing_values
            },
            "tables": [
                {
                    "title": "变量均值",
                    "header": mean_table[0],
                    "rows": mean_table[1:]
                },
                {
                    "title": "协方差矩阵",
                    "header": cov_table[0],
                    "rows": cov_table[1:]
                },
                {
                    "title": "相关系数矩阵",
                    "header": corr_table[0],
                    "rows": corr_table[1:]
                }
            ]
        }
        
    except Exception as e:
        return {"error": str(e)}

if __name__ == '__main__':
    test_options = {
        'data_path': 'test_data.csv',
        'chart_type': '多变量条图',
        'x_var': '地区',
        'y_var': '食品'
    }
    
    result = generate_visualization(test_options)
    
    if "error" in result:
        print("运行出错:", result["error"])
    else:
        print("指标计算成功:", result["metrics"])
        print("表格生成成功, 包含表格数量:", len(result["tables"]))
        
        with open("test_output.svg", "w", encoding="utf-8") as f:
            f.write(result["svgs"][0])
        print("\n图表已保存到当前目录下的 test_output.svg，你可以双击用浏览器打开查看图表是否正确。")