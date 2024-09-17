import sys
from PyPDF2 import PdfReader
def process_pdf(file_path):
    print(f"Processing PDF: {file_path}")
    # 在這裡添加處理 PDF 的邏輯
    # 例如：讀取 PDF 檔案、分析、轉換等等

if __name__ == "__main__":
    # 接收傳入的 PDF 檔案路徑
    if len(sys.argv) > 1:
        pdf_file = sys.argv[1]
        print(pdf_file)
    else:
        print("No PDF file path provided.")
