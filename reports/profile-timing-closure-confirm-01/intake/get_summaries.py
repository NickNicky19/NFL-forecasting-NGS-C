from fetch_exact import fetch
A='NickNicky19/NFL-forecasting';REF='a969aeafa945edec686f5b54a9bc64f99bfa4bf0';P='reports/abc-championship/profile-increment-to-release-01/closure-next-02/'
for path,name in [('c03-public-v1/CUMULATIVE_ALL_PROCEDURES_001.csv','A_C03_CUMULATIVE'),('b-completion-public-v2/ANNUAL_ACTUAL_W1_W5_001.csv','A_BCMP_ANNUAL1'),('b-completion-public-v2/ANNUAL_ACTUAL_W1_W5_002.csv','A_BCMP_ANNUAL2'),('EXECUTION_SUMMARY_V1.json','A_SUMMARY'),('freshness-public-v1/ALL_SUMMARIES_001.csv','A_TIMING_FIRST_SHARD')]:
 d=fetch(A,REF,P+path,name);print(name,len(d))
