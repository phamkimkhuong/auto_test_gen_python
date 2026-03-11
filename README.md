# Auto Test Generator PoC (AST-Based)

Công cụ mô phỏng **tự động sinh unit test cơ bản cho Python** bằng **phân tích tĩnh (static analysis)** dựa trên mô-đun `ast` của Python, **không sử dụng AI/LLM**.

Mục tiêu của dự án là xây dựng một **Proof of Concept (PoC)** có thể:
- phân tích cấu trúc mã nguồn Python ở mức hàm,
- trích xuất tham số, kiểu dữ liệu, nhánh điều kiện cơ bản và đường đi có thể phát sinh ngoại lệ,
- từ đó sinh ra các test `pytest` ở mức **smoke test**, **boundary test** và một phần **exception test** trong phạm vi đã kiểm soát.

> Đây là công cụ PoC phục vụ mục tiêu nghiên cứu/demo đồ án, **không phải** bộ sinh test tổng quát cho mọi codebase Python.

---

## 1. Mục tiêu nghiên cứu

Đề tài hướng tới việc trả lời câu hỏi:

**Liệu có thể tự động sinh unit test cơ bản cho Python chỉ bằng static analysis trên AST, không cần AI/LLM hay không?**

Từ câu hỏi đó, mục tiêu nghiên cứu của đồ án gồm:

1. **Phân tích cấu trúc mã nguồn Python** ở mức hàm bằng thư viện `ast`.
2. **Trích xuất thông tin tĩnh** từ hàm:
   - tên hàm,
   - tham số và type hints,
   - giá trị mặc định,
   - kiểu trả về,
   - một số nhánh điều kiện đơn giản,
   - khả năng phát sinh ngoại lệ.
3. **Sinh dữ liệu kiểm thử heuristic** dựa trên:
   - type hints,
   - literal xuất hiện trong điều kiện `if`,
   - ranh giới lân cận của các literal số/chuỗi.
4. **Tự động sinh test bằng `pytest`** theo hướng an toàn:
   - ưu tiên suite chạy xanh trong phạm vi đầu vào đã khóa,
   - không sinh assertion mang tính suy đoán nếu không đủ căn cứ.
5. **Tích hợp đo coverage và chạy CI** để chứng minh công cụ hoạt động như một pipeline kiểm thử tự động ở mức PoC.

---

## 2. Phương pháp

Công cụ được xây dựng theo hướng **AST-based static analysis**.

### 2.1. Phân tích AST
Mã nguồn đầu vào được parse thành cây cú pháp bằng mô-đun `ast` của Python. Từ cây cú pháp này, công cụ duyệt các node như:

- `FunctionDef`
- `If`
- `Compare`
- `Raise`
- `arguments`
- `Constant`

để trích xuất metadata phục vụ sinh test.

### 2.2. Phạm vi phân tích
Công cụ hiện tập trung vào:

- **top-level synchronous functions**
- các nhánh điều kiện đơn giản dạng:
  - `arg == constant`
  - `arg != constant`
  - `arg < constant`
  - `arg <= constant`
  - `arg > constant`
  - `arg >= constant`
- một số trường hợp phát hiện `raise` cơ bản trong thân hàm

### 2.3. Sinh dữ liệu kiểm thử
Dữ liệu kiểm thử được tạo theo 2 nguồn:

**(a) Heuristic theo kiểu dữ liệu**
- `int` → `0`, `1`, `-1`
- `float` → `0.0`, `1.5`, `-2.5`
- `str` → `""`, `"test"`, `"Tiếng Việt"`, `" "`
- `bool` → `True`, `False`
- `list` → `[]`, `[1, 2, 3]`
- `dict` → `{}`, `{"k": 1}`

**(b) Dynamic boundary injection**
Nếu parser phát hiện điều kiện như `code == 200` hoặc `age < 18`, công cụ sẽ sinh thêm dữ liệu biên có liên quan để phục vụ boundary test hoặc exception test.

### 2.4. Sinh mã test
Từ metadata trích xuất được, công cụ sinh các test `pytest` theo 3 hướng:

- **Smoke test**: chạy một bộ input an toàn để xác nhận hàm thực thi được
- **Boundary test**: chạy nhiều bộ input ở biên bằng `pytest.mark.parametrize`
- **Exception test**: chỉ sinh khi công cụ suy ra được trigger tuple và kiểu ngoại lệ đủ an toàn

Nếu công cụ **không đủ cơ sở để suy ra assertion đáng tin cậy**, nó sẽ:
- hạ test về execution-only smoke test, hoặc
- dùng `pytest.skip(...)` / `@pytest.mark.skip(...)`

thay vì sinh assert sai.

---

## 3. Kết quả mong đợi

Sau khi chạy công cụ, kết quả mong đợi gồm:

1. **Sinh tự động file test `pytest`** từ các file Python mẫu.
2. **Thực thi được test suite** trong phạm vi PoC đã khóa.
3. **Đo được coverage** bằng `pytest-cov`.
4. **Có thể chạy tự động trên GitHub Actions** khi push code.
5. Chứng minh được một luận điểm nghiên cứu quan trọng:

> Static analysis dựa trên AST có thể hỗ trợ sinh unit test cơ bản trong phạm vi hẹp, có kiểm soát đầu vào, mà không cần dùng AI/LLM.

---

## 4. Tính năng nổi bật

- **No AI / No LLM**
- **AST-based static analysis**
- **Rich CLI Interface**: Progress bar và bảng tổng kết trực quan.
- **Smart Test Dashboard**: Tự động sinh báo cáo HTML chuyên nghiệp, phân loại test case theo file.
- **Dry-run mode** để audit metadata trước khi sinh test.
- **Boundary-aware test generation**.
- **Tích hợp `pytest`, `pytest-cov`, GitHub Actions**.

---

## 5. Cấu trúc thư mục

```text
auto_test_gen/
├── demo_inputs/
│   ├── condition_utils.py
│   ├── dict_utils.py
│   ├── list_utils.py
│   ├── math_utils.py
│   └── string_utils.py
├── core_engine/
│   ├── __init__.py
│   ├── cli.py
│   ├── ast_parser.py
│   ├── heuristics.py
│   └── code_generator.py
├── tests_output/
├── .github/
│   └── workflows/
│       └── ci.yml
├── requirements.txt
└── README.md
```
## 6. Bộ demo đầu vào

Bộ `demo_inputs/` được dùng làm **Data Calibration** để chứng minh công cụ hoạt động đúng kỹ thuật trong phạm vi PoC.

Ví dụ một số hàm mẫu hiện có:

### `condition_utils.py`
```python
def check_status(code: int) -> str:
    if code == 200:
        return "OK"
    elif code == 404:
        return "Not Found"
    return "Unknown"
```

### `math_utils.py`
```python
def add(a: int, b: int) -> int:
    return a + b

def divide(a: int, b: int) -> float:
    if b == 0:
        return 0.0
    return a / b
```

### `string_utils.py`
```python
def greet(name: str) -> str:
    if name == "":
        return "Hello, Guest!"
    return f"Hello, {name}!"
```

Các file demo được thiết kế để:
- Có **type hints** rõ ràng.
- Không phụ thuộc I/O phức tạp.
- Ưu tiên **pure functions**.
- Có một số nhánh so sánh đơn giản để parser AST nhận diện tốt.

---

## 7. Phạm vi hỗ trợ

### Hỗ trợ tốt
- **Top-level functions**: Cả đồng bộ (`def`) và bất đồng bộ (`async def`).
- **Type hints cơ bản**: `int`, `float`, `str`, `bool`, `list`, `dict`.
- **Điều kiện `if` đơn giản** với literal (số, chuỗi, bool).
- **Raise-path cơ bản**: Nhận diện được exception type khi gặp lệnh `raise`.
- **Tự động sinh bộ tests**: Bao gồm smoke test và boundary tests (sử dụng `pytest.mark.parametrize` và `@pytest.mark.asyncio`).

### Ngoài phạm vi (Hoặc hỗ trợ hạn chế)
- **Class methods**: Các phương thức trong class (`self`).
- **Nested functions**: Hàm lồng nhau.
- **Framework-specific code**: Mã nguồn phụ thuộc vào Django, Flask, FastAPI.
- **I/O nặng**: Các thao tác liên quan đến Network, Database, File System.
- **Symbolic execution**: Giải quyết các ràng buộc đường đi phức tạp.
- **Assertion nghiệp vụ sâu**: Kiểm tra logic nghiệp vụ phức tạp bên trong kết quả trả về.

---

## 8. Cài đặt

Yêu cầu: **Python 3.10+**

### Cách 1: Cài đặt chính thức (Khuyên dùng)
```bash
git clone https://github.com/your-username/auto_test_gen_python.git
cd auto_test_gen_python
# Cài đặt và tự động tải mọi dependencies (pytest-html, json-report, rich,...)
pip install .
```

### Cách 2: Cài đặt dependencies thủ công
```bash
pip install -r requirements.txt
```

---

Sau khi cài đặt bằng `pip install .`, bạn có thể dùng lệnh `auto-test-gen` ở bất cứ đâu.

### 9.1. Lệnh cơ bản (Sinh test & Chạy ngay)
```bash
# Tự động quét demo_inputs, sinh test vào tests_output và thực thi
auto-test-gen demo_inputs --run
```

### 9.2. Xuất báo cáo Dashboard & Coverage
```bash
# Sinh dashboard HTML (test_dashboard.html) và báo cáo coverage
auto-test-gen demo_inputs --run --report html
```

### 9.3. Lệnh dự phòng (Nếu không cài package)
```bash
# Sử dụng module path trực tiếp
python -m core_engine.cli demo_inputs --out tests_output --module demo_inputs --run
```

---

## 10. Các tính năng nâng cao (Milestone 3)

### Hỗ trợ Async/Await
Công cụ đã có thể xử lý các hàm `async def`. Nó sẽ tự động:
- Thêm dấu `@pytest.mark.asyncio`.
- Sử dụng từ khóa `await` khi gọi hàm trong code test.
- Đảm bảo môi trường chạy async thông qua `pytest-asyncio`.

###  Giao diện Rich CLI
- **Progress Bar**: Hiển thị tiến trình quét file thời gian thực.
- **Summary Table**: Bảng tổng kết kết quả đẹp mắt với màu sắc phân biệt.
- **Auto-run**: Tích hợp luồng chạy kiểm thử ngay sau khi sinh mã.

### Đóng gói Thư viện
Bạn có thể cài đặt công cụ như một thư viện CLI hệ thống:
```bash
pip install .
# Sau đó chạy lệnh trực tiếp:
auto-test-gen demo_inputs --run
```
---

## 11. Ví dụ generated test

Dựa trên code gốc, công cụ sẽ tự động tính toán các giá trị biên (boundary):

**Mã nguồn gốc (`check_status`):**
```python
def check_status(code: int) -> str:
    if code == 200:
        return "OK"
    elif code == 404:
        return "Not Found"
    return "Unknown"
```

**Mã test sinh ra:**
```python
import pytest
from demo_inputs.condition_utils import check_status

def test_check_status_smoke():
    code = 0
    result = check_status(code)
    assert isinstance(result, str)

@pytest.mark.parametrize('code', [0, 1, -1, 199, 200, 201], ids=['code=0', 'code=1', 'code=-1', 'code=199', 'code=200', 'code=201'])
def test_check_status_boundary(code):
    result = check_status(code)
    assert isinstance(result, str)
```

---

## 12. Tích hợp CI với GitHub Actions

Dự án hỗ trợ sẵn pipeline CI để tự động hóa việc sinh test và đo coverage trên mỗi lần push:

```yaml
name: Python Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: python -m core_engine.cli demo_inputs --out tests_output --module demo_inputs
      - run: pytest tests_output/ --cov=demo_inputs --cov-report=term-missing
```

---

## 13. Hạn chế của PoC

Đây là một PoC mang tính nghiên cứu nên còn các giới hạn:
-  Chưa hỗ trợ toàn bộ pattern của Python AST.
-  Chưa sinh được assertion nghiệp vụ sâu.
-  Chưa thay thế được con người trong thiết kế test case phức tạp.
-  Chưa phù hợp cho production codebase lớn và nhiều side effects.
-  Chưa phải symbolic execution engine.

Tuy nhiên, trong phạm vi đầu vào đã khóa, công cụ vẫn chứng minh được tính khả thi của hướng tiếp cận này.

---

## 14. Kết luận

Dự án này chứng minh rằng có thể xây dựng một công cụ tự động sinh unit test cơ bản cho Python bằng **static analysis trên AST**, trong phạm vi nhỏ, có kiểm soát, và không cần AI/LLM.

**Giá trị chính của đề tài:**
1. Tạo ra một kiến trúc thử nghiệm có thể mở rộng.
2. Chứng minh tính khả thi của hướng **AST-based test generation**.
3. Làm nền cho các nghiên cứu sâu hơn về **path constraint solving** và **symbolic execution**.

---

## 15. Tài liệu tham khảo chính

- [Python ast documentation](https://docs.python.org/3/library/ast.html)
- [Python argparse documentation](https://docs.python.org/3/library/argparse.html)
- [pytest documentation](https://docs.pytest.org/)
- [pytest-cov documentation](https://pytest-cov.readthedocs.io/)
- [GitHub Actions Python testing guide](https://docs.github.com/en/actions/automating-builds-and-tests/building-and-testing-python)
