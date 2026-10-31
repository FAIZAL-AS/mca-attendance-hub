import csv
import re

raw_data = """
S.no,Registration Number,Name,Course,section,
1,RTC2026MCA024,Adheeswaran K,MCA,A,
2,RTC2026MCA098,Adhithya K,MCA,A,
3,RTC2026MCA072,Adhithya K,MCA,A,
4,RTC2026MCA029,Adithya C Lijish,MCA,A,
5,RTC2026MCA077,Afrin S,MCA,A,
6,RTC2026MCA066,Ajay Kumar S,MCA,A,
7,RTC2026MCA013,Ajith Arvind Yadav A,MCA,A,
8,RTC2026MCA071,Akshaya S,MCA,A,
9,RTC2026MCA019,Amarnath S,MCA,A,
10,RTC2026MCA086,Anandha Kannan M,MCA,A,
11,RTC2026MCA052,Ananya S,MCA,A,
12,RTC2026MCA055,Arockia Jerin Infant J,MCA,A,
13,RTC2026MCA005,Chandru C,MCA,A,
14,RTC2026MCA105,Chandru S,MCA,A,
15,RTC2026MCA073,Deepak Kumar G,MCA,A,
16,RTC2026MCA032,Deepanraja E,MCA,A,
17,RTC2026MCA022,Dhanusri P,MCA,A,
18,RTC2026MCA021,Dharshani R,MCA,A,
19,RTC2026MCA116,Dharshini R,MCA,A,
20,RTC2026MCA095,Dharshini R,MCA,A,
21,RTC2026MCA008,Dhinesh Aravindh,MCA,A,
22,RTC2026MCA103,Divya Priya G,MCA,A,
23,RTC2026MCA065,Ebhi Justin J,MCA,A,
24,RTC2026MCA123,Gayathri T,MCA,A,
25,RTC2026MCA070,Giniha N,MCA,A,
26,RTC2026MCA056,Giridharan M,MCA,A,
27,RTC2026MCA089,Gokul Prasath S,MCA,A,
28,RTC2026MCA078,Gopika B,MCA,A,
29,RTC2026MCA092,Hari Mb,MCA,A,
30,RTC2026MCA100,Hariharan S,MCA,A,
31,RTC2026MCA121,Hariharasudhan K,MCA,A,
32,RTC2026MCA091,Harini B,MCA,A,
33,RTC2026MCA037,Harishnath M,MCA,A,
34,RTC2026MCA0125,Harishma S,MCA,A,
35,RTC2026MCA076,Hassan Wajith,MCA,A,
36,RTC2026MCA017,Iniyavan C,MCA,A,
37,RTC2026MCA058,Jason Infant Roy S,MCA,A,
38,RTC2026MCA111,Jawahar S,MCA,A,
39,RTC2026MCA118,Jaya Suriya C R,MCA,A,
40,RTC2026MCA043,Jayakaviya M,MCA,A,
41,RTC2026MCA109,Jayakiruthika G,MCA,A,
42,RTC2026MCA018,Jenitha C,MCA,A,
43,RTC2026MCA102,Jugi J,MCA,A,
44,RTC2026MCA041,Kaleeswaran M,MCA,A,
45,RTC2026MCA026,Kanishka E,MCA,A,
46,RTC2026MCA011,Karthigaiselvam M,MCA,A,
47,RTC2026MCA101,Kavin M R,MCA,A,
48,RTC2026MCA051,Kavitha R,MCA,A,
49,RTC2026MCA030,Kaviya R,MCA,A,
50,RTC2026MCA064,Kaviya Shri A. S,MCA,A,
51,RTC2026MCA034,Kaviya T,MCA,A,
52,RTC2026MCA107,Kaviyarasan S,MCA,A,A
53,RTC2026MCA069,Keerthi Vasan Ks,MCA,A,
54,RTC2026MCA114,Kishore M,MCA,A,
55,RTC2026MCA025,Kokila R,MCA,A,
56,RTC2026MCA006,Lakshana S,MCA,A,
57,RTC2026MCA124,Madhan Raj G,MCA,A,
58,RTC2026MCA099,Madhana Gurus Ray R,MCA,A,
59,RTC2026MCA014,Madhumitha S,MCA,A,
60,RTC2026MCA038,Mahesh K,MCA,A,
61,RTC2026MCA117,Manickam N,MCA,A,
62,RTC2026MCA080,Manoharan S,MCA,A,
1,RTC2026MCA059,Mehana A,MCA,B
2,RTC2026MCA120,Mohammed Afsar H,MCA,B
3,RTC2026MCA054,Mohammed Faizal AS,MCA,B
4,RTC2026MCA085,Mohammed Mahful M N,MCA,B
5,RTC2026MCA106,Mohammedabsar M,MCA,B
7,RTC2026MCA045,Nandhakumar S,MCA,B
8,RTC2026MCA108,Naveen Raj Su,MCA,B
9,RTC2026MCA046,Naveenkumar M,MCA,B
10,RTC2026MCA040,Navin Kumar Ck,MCA,B
11,RTC2026MCA053,Neha A,MCA,B
12,RTC2026MCA062,Nivas S,MCA,B
13,RTC2026MCA082,Omer Mohamed Omer Mohamed,MCA,B
14,RTC2026MCA075,Padma Sree N,MCA,B
15,RTC2026MCA004,Pandi Amirth Raj R,MCA,B
16,RTC2026MCA039,Poojasri S,MCA,B
17,RTC2026MCA094,Pradeep V,MCA,B
18,RTC2026MCA090,Prasanth S,MCA,B
19,RTC2026MCA001,Priscilla V,MCA,B
20,RTC2026MCA035,Rachana V,MCA,B
21,RTC2026MCA060,Raghavi K,MCA,B
22,RTC2026MCA122,Ram Ganesh,MCA,B
23,RTC2026MCA028,Rasvanth A,MCA,B
24,RTC2026MCA074,Ravi Shankar S,MCA,B
25,RTC2026MCA023,Rishi Kumar,MCA,B
26,RTC2026MCA002,Ritheesh V,MCA,B
27,RTC2026MCA012,Rubendhiran P,MCA,B
28,RTC2026MCA083,Sabareesh Balan M,MCA,B
29,RTC2026MCA009,Sabari J L,MCA,B
30,RTC2026MCA063,Sachin Sarabeshwarar M,MCA,B
31,RTC2026MCA093,Sachin T,MCA,B
32,RTC2026MCA097,Sagadevan  H,MCA,B
33,RTC2026MCA113,Sajeetha P,MCA,B
34,RTC2026MCA112,Sakthi Bharani S,MCA,B
35,RTC2026MCA088,Sanjay V,MCA,B
36,RTC2026MCA084,Santhiya R,MCA,B
37,RTC2026MCA042,Santhosh Kumar G,MCA,B
38,RTC2026MCA007,Santhosh M,MCA,B
39,RTC2026MCA096,Sasikumar P,MCA,B
40,RTC2026MCA050,Sathiyamoorthy  S,MCA,B
41,RTC2026MCA016,Sathyaseelan M,MCA,B
42,RTC2026MCA033,Shobika M,MCA,B
43,RTC2026MCA047,Sindhuja Ck,MCA,B
44,RTC2026MCA081,Sivanesan S,MCA,B
45,RTC2026MCA015,Sivasankari  M,MCA,B
46,RTC2026MCA036,Suba Harini S,MCA,B
47,RTC2026MCA044,Subasri M,MCA,B
48,RTC2026MCA057,Sudharsan P,MCA,B
49,RTC2026MCA110,Suganth A,MCA,B
50,RTC2026MCA115,Tanushri Mg,MCA,B
51,RTC2026MCA119,Thamarai Selvam D,MCA,B
52,RTC2026MCA067,Vadhana Shree S,MCA,B
53,RTC2026MCA068,Vanaja T,MCA,B
54,RTC2026MCA031,Varsha B,MCA,B
55,RTC2026MCA003,Veeralakshmi M,MCA,B
56,RTC2026MCA061,Vellai Chamy M,MCA,B
57,RTC2026MCA104,Velmurugan Kanagaraj,MCA,B
58,RTC2026MCA027,Vibahar S,MCA,B
59,RTC2026MCA048,Vidhusha Jothikumar,MCA,B
60,RTC2026MCA079,Vignesh R,MCA,B
61,RTC2026MCA010,Vijaya Ragavi J,MCA,B
62,RTC2026MCA087,Vinoth Kumar G,MCA,B
"""

rows = []
for line in raw_data.strip().splitlines():
    parts = [p.strip() for p in line.split(",") if p.strip()]
    if len(parts) >= 5 and parts[1].startswith("RTC2026"):
        sno = parts[0]
        reg_no = parts[1]
        name = parts[2]
        course = parts[3]
        section = parts[4].upper()
        if section not in ["A", "B"]:
            section = "A" if "A" in parts[4:] else "B"
        rows.append([sno, reg_no, name, course, section])

out_path = r"C:\Users\USER\.gemini\antigravity\scratch\mca_attendance_app\students.csv"
with open(out_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["sno", "reg_no", "name", "course", "section"])
    writer.writerows(rows)

print(f"Wrote {len(rows)} records successfully to {out_path}")
