from fetch_exact import fetch
A='NickNicky19/NFL-forecasting';AR='a969aeafa945edec686f5b54a9bc64f99bfa4bf0';B='NickNicky19/NFL-forecasting-V2';BR='b616b0073a26cb95011df9c53b86ae0693437f15';AP='reports/abc-championship/profile-increment-to-release-01/closure-next-02/';BP='reports/profile-increment-closure-next-02/B/'
for repo,ref,path,name in [
(A,AR,AP+'EXECUTED_CLOSURE_CHECKPOINT_V1.md','A_REPORT'),(A,AR,AP+'freshness-public-v1/MANIFEST_V1.json','A_TIMING_MANIFEST'),(A,AR,AP+'c03-public-v1/MANIFEST_V1.json','A_C03_MANIFEST'),(A,AR,AP+'b-completion-public-v2/MANIFEST.json','A_BCMP_MANIFEST'),
(B,BR,BP+'ALIGNED_FRESHNESS_REPORT.md','B_REPORT'),(B,BR,BP+'PRODUCT_DECISIONS_V1.json','B_DECISIONS'),(B,BR,BP+'SAVED_TIMING_OUTPUT_HANDOFF_V1.json','B_TIMING_HANDOFF')]:
 d=fetch(repo,ref,path,name);print(name, list(d)[:15] if isinstance(d,dict) else len(d))
