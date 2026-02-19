"""测试 emo 标签清理正则"""
import re

tests = [
    '[emo:happy]!你好',
    '[emo:sad]？怎么了', 
    '[emo:wink]~嗨',
    '你好[emo:happy]！',
    '[emo:blush]，我很害羞',
    '[emo:happy]Hello!',
    '?[emo:surprised]什么',
]

for t in tests:
    # 第一步：移除 emo 标签及其后可能跟随的标点
    cleaned = re.sub(r'\[emo:\w+\]\s*[!?！？。，、~]*', '', t)
    # 第二步：移除句首残留的标点
    cleaned = re.sub(r'^[!?！？。，、~\s]+', '', cleaned)
    cleaned = cleaned.strip()
    print(f'{t!r:40} -> {cleaned!r}')
