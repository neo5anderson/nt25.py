from nt25 import fio, draw, DType

csv = fio.getCSV('ds/92.csv', width=11, startLine=1)
if isinstance(csv, list):
  P = csv[0]
  Pa = csv[1]
  R = csv[9]

  ref = draw.draw(DType.dot3d, P, Pa, R)
  draw.draw(DType.wireframe, P, Pa, R, ref=ref, color='orange')
  draw.show()
