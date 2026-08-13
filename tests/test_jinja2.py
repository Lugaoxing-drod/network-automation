from jinja2 import Template

# 从文件读取模板（真实用法）
with open('../templates/vlan_config.j2', 'r', encoding='utf-8') as f:
    template = Template(f.read())

# 准备变量
variables = {
    'vlan_id': 100,
    'vlan_name': 'Office_5F',
    'interface': 'GigabitEthernet0/0/1',
}

# 渲染
config = template.render(**variables)

# 输出
print(config)