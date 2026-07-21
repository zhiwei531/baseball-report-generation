# Metrics Reference

The executable authority is `scripts/metric_registry.py`; formulas, required
points/channels, coordinate profile, side rule, missing-data policy,
implementation, and report options are immutable fields tested in
`tests/test_metric_registry.py`. All use the current right-handed/right-throwing
`legacy_vicon_z_up_mm` profile unless the definition explicitly says otherwise.

## Batting report metrics (17)

| ID | 中文 | English | Unit | Event |
|---|---|---|---|---|
| ready_com_height_ratio | 重心高度 | Ready Body Height | height_ratio | Ready Position |
| ready_rear_hip_flexion_deg | 后髋屈曲角 | Rear Hip Flexion | deg | Ready Position |
| ready_rear_knee_flexion_deg | 后膝屈曲角 | Rear Knee Flexion | deg | Ready Position |
| ready_hip_shoulder_separation_deg | 髋肩分离角 | Hip-Shoulder Separation | deg | Ready Position |
| ready_bat_tilt_deg | 球棒倾角 | Bat Angle at Ready | deg | Ready Position |
| ready_hand_height_ratio | 握棒手高度 | Hand Height at Ready | height_ratio | Ready Position |
| contact_bat_speed_kmh | 球棒速度 | Bat Speed | km/h | Contact Position |
| contact_attack_angle_deg | 挥棒路径角 | Attack Angle | deg | Contact Position |
| contact_pelvis_rotation_open_deg | 骨盆旋转角 | Pelvis Rotation | deg | Contact Position |
| contact_torso_rotation_open_deg | 躯干旋转角 | Torso Rotation | deg | Contact Position |
| contact_front_knee_flexion_deg | 前膝屈曲角 | Front Knee Flexion | deg | Contact Position |
| ready_to_contact_head_displacement_mm | 头部位移 | Ready-to-Contact Head Displacement | mm | Ready to Contact |
| coach_high_com_risk_index | 重心偏高指数 | High Center of Mass Risk | 0-100 risk | Ready Position |
| coach_rear_elbow_height_diff_mm | 后肘高度差（掉肘） | Rear Elbow Height Difference | mm | Ready Position |
| coach_bat_loading_angle_to_catcher_deg | 球棒加载角（引棒不足） | Bat Loading Angle | deg | Ready Position |
| coach_rollover_forearm_roll_velocity_deg_s | 手腕翻转角速度（翻腕） | Forearm Roll Velocity | deg/s | Contact Position |
| coach_hitting_zone_stability_score | 击球区稳定性 | Hitting Zone Stability | 0-100 score | High-Speed Hitting Zone |

## Pitching report metrics (18)

| ID | 中文 | English | Unit | Event |
|---|---|---|---|---|
| knee_height_pct | 抬腿高度 | Knee Lift Height | pct | peak_knee |
| front_knee_peak_deg | 前腿收紧 | Lead-Knee Tuck | deg | peak_knee |
| rear_knee_peak_deg | 后腿蓄力 | Rear-Leg Load | deg | peak_knee |
| stride_distance_pct | 跨步距离 | Stride Distance | pct | foot_plant |
| stride_direction_deg | 跨步方向 | Stride Direction | deg | foot_plant |
| front_knee_plant_deg | 前膝屈曲 | Lead-Knee Flexion | deg | foot_plant |
| rear_knee_plant_deg | 后膝屈曲 | Rear-Knee Flexion | deg | foot_plant |
| elbow_vs_shoulder_cm | 投球肘相对肩线 | Throwing-Elbow Height | cm | foot_plant |
| shoulder_abduction_plant_deg | 肩外展 | Shoulder Abduction | deg | foot_plant |
| front_knee_release_deg | 出手前膝角 | Release Lead-Knee Angle | deg | release |
| front_knee_change_plant_to_release_deg | 落地到出手前膝变化 | Lead-Knee Change: Plant to Release | deg | release |
| shoulder_abduction_release_deg | 出手肩外展 | Release Shoulder Abduction | deg | release |
| elbow_flex_release_deg | 出手肘屈曲 | Release Elbow Flexion | deg | release |
| arm_slot_deg | 出手手臂角度 | Release Arm Angle | deg | release |
| release_height_pct | 出手高度 | Release Height | pct | release |
| hand_speed_kmh | 出手手速 | Release Hand Speed | kmh | release |
| max_hss_deg | 最大髋肩分离 | Maximum Hip-Shoulder Separation | deg | full motion |
| hss_release_amount_deg | 髋肩分离释放量 | Hip-Shoulder Separation Release | deg | full motion |

Pitching also has 23 typed auxiliary values used by charts/narratives and 11
generic Vicon diagnostic units; they are deliberately outside the 18 report
cards. Hand speed is a throwing-hand marker proxy, not ball speed. Batting
Contact remains the lowest-`Bat1_Z` proxy and bat speed is the event-window
mean, not maximum swing speed.
