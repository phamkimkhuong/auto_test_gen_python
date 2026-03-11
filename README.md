# Auto Test Generator PoC (AST Based)

Công cụ mô phỏng tự động sinh test case cơ bản (test skeleton, assertions cơ bản, mock data cho types) sử dụng `ast` thuần túy của Python. 

## Tính Năng Nổi Bật
- **No AI / LLM needed**: Hoàn toàn dựa trên phân tích tĩnh (Static Analysis).
- **PoC Coverage**: Tối ưu khả năng đo phủ mã nguồn (Coverage) đối với các Pure Functions có Type Hints chuẩn.
- **Tích Hợp Tự Động**: Tích hợp luồng CI trực tiếp vào GitHub Actions (chạy pytest, đo coverage mỗi khi push).

## Cấu Trúc Thư Mục
```text
auto_test_gen/
├── demo_inputs/             # Chứa 5 file code chuẩn do BẠN viết (Input)
│   ├── math_utils.py        # Demo các hàm toán học thuần túy
│   └── string_utils.py      # Demo các hàm thao tác chuỗi
├── core_engine/             # Trái tim của công cụ
│   ├── __init__.py
│   ├── cli.py               # Entry point: Xử lý tham số dòng lệnh & UI/UX terminal
│   ├── ast_parser.py        # Logic dùng thư viện `ast` bóc tách hàm, tham số, Type Hints
│   ├── heuristics.py        # "Bộ não giả": Ánh xạ Type Hint -> Test Data (VD: int -> 0, 1, -1)
│   └── code_generator.py    # Lắp ghép dữ liệu vào template để sinh code `pytest`
├── tests_output/            # Thư mục đích chứa các file test tự động sinh ra (Output)
├── .github/
│   └── workflows/
│       └── ci.yml           # File CI/CD chạy pytest & coverage tự động
├── requirements.txt         # Chứa: pytest, pytest-cov, rich (cho UI terminal)
└── README.md                # Tài liệu hướng dẫn sử dụng (Rất quan trọng cho đồ án)
```

## Cài đặt
1. Cài đặt các thư viện cần dùng (Nên chạy trên `Python 3.10+`):
```bash
pip install -r requirements.txt
```

2. Cách sử dụng (Demo):
```bash
# Lệnh chạy sinh test cho toàn bộ thư mục demo
python -m core_engine.cli demo_inputs --out tests_output --module demo_inputs

# Chạy test và xuất coverage
pytest tests_output/ --cov=demo_inputs --cov-report=term-missing
```

## Chú Ý Quan Trọng
Đây là bộ **Dữ liệu hiệu chuẩn (Data Calibration)** để chứng minh công cụ hoạt động đúng kỹ thuật với các chuẩn đầu vào (Type Hints, Không I/O, Pure Functions). Công cụ KHÔNG thay thế lý thuyết nghiên cứu mà đóng vai trò như một môi trường bằng chứng (Proof of Concept) cho một kiến trúc kiểm thử tự động.
