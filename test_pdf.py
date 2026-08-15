from modules import pdf_exporter

out = 'test_outputs/sample_report.pdf'
headers = ['ID','Nombre','Cantidad','Precio (Bs)']
rows = [[1,'Producto A',10,100.5],[2,'Producto B con descripción larga que debe envolver en celdas',2,250.0]]
res = pdf_exporter.export_table_to_pdf(out,'Reporte de Prueba',headers,rows,company_info={'name':'Empresa X','tax_id':'J-11111111-1'})
print(res)

