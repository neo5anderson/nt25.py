from nt25 import fio

import json
import argparse

import requests


kEncoding = "gbk"
kWGSName = "WGS-84"

kMaxTranCount = 50

kWGSCode = 4326
k50NCode = 32650
kCGS2000Z20Code = 4498
kCGS2000Z21Code = 4499

kURLFormatter = (
  "https://api.maptiler.com/coordinates/transform/"
  + "{cs}.json?key={key}&s_srs={s}&t_srs={t}"
)


def genCs4Tran(coordinates):
  cs = []

  for i in range(min(len(coordinates), kMaxTranCount)):
    c = coordinates[i]
    cs.append("{0},{1}".format(c[0], c[1]))

  return ";".join(cs)


def fetchResult(url):
  result = {}
  res = requests.get(url)

  try:
    result = json.loads(res.text)
  except Exception as e:
    print(e, "\n\t", res.text)

  return result


def transform(key, coordinates, startCode, toCode):
  results = []

  cc = [
    coordinates[i : i + kMaxTranCount]
    for i in range(0, len(coordinates), kMaxTranCount)
  ]

  for c in cc:
    url = kURLFormatter.format(cs=genCs4Tran(c), key=key, s=startCode, t=toCode)
    result = fetchResult(url)

    if result and result["results"] and result["results"][0]["x"] is not None:
      results.extend(result["results"])

  for i in range(len(results)):
    results[i]["z"] = coordinates[i][2] if len(coordinates[i]) > 2 else 0

  return results


def main():
  parse = argparse.ArgumentParser(
    description="Map Transform tool, "
    "from https://docs.maptiler.com/cloud"
    "/api/coordinates/#transform-coordinates"
  )

  #  default=kKey
  parse.add_argument("-k", "--key", type=str, help="MapTiler key", required=True)
  parse.add_argument("-i", "--input", type=str, required=True, help="input file")
  parse.add_argument("-o", "--output", type=str, help="output file", default="out.csv")
  parse.add_argument(
    "-s", "--start", type=str, default="4498", help="transform start code"
  )
  parse.add_argument("-t", "--to", type=str, default="4236", help="transform code to")

  args = parse.parse_args()

  key = args.key
  input = args.input
  output = args.output
  start = args.start
  to = args.to

  csv = fio.getCSV(input, width=3, startLine=1)

  if csv is not None:
    coordinates = []
    for i in range(len(csv[0])):
      coordinates.append((csv[0][i], csv[1][i], csv[2][i]))

    result = transform(key, coordinates, start, to)

    if len(result) > 0:
      content = list(map(lambda r: (r["x"], r["y"], r["z"]), result))
      fio.saveCSV(content, output, colsInline=False)
      print(f"Saved {len(result)} rows in {output}")


if __name__ == "__main__":
  main()
