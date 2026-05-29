
import json

# 读取文件
with open('data/heroes.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

# 调整根级字段顺序
root_keys = ['heroes', 'total_heroes', 'heroDetailUrlTemplate', 'skin_image_base_urls', 'defaultHeroNames']
new_root = {key: data[key] for key in root_keys}

# 调整每个皮肤对象的字段顺序
for hero in new_root['heroes']:
    if 'skins' in hero:
        new_skins = []
        for skin in hero['skins']:
            # 确保字段顺序为 name, image_id, image
            new_skin = {
                'name': skin['name'],
                'image_id': skin.get('image_id', '')
            }
            if 'image' in skin:
                new_skin['image'] = skin['image']
            new_skins.append(new_skin)
        hero['skins'] = new_skins

# 保存文件
with open('data/heroes.json', 'w', encoding='utf-8') as f:
    json.dump(new_root, f, ensure_ascii=False, indent=2)

print("字段顺序调整完成")
