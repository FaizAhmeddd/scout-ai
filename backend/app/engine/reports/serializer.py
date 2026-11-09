from typing import Any

from app.engine.fusion.report_builder import MatchReport, PlayerReport


def _round(value: float | None, digits: int = 1) -> float | None:
    return None if value is None else round(float(value), digits)


def player_to_dict(player: PlayerReport) -> dict[str, Any]:
    kin = player.metrics.kinematics
    pose = player.metrics.pose
    return {
        "player_id": player.player_id,
        "label": player.label,
        "jersey_number": player.jersey_number,
        "team_id": player.metrics.player.team_id,
        "tracker_fragments": player.metrics.player.source_track_ids,
        "on_screen_s": _round(player.metrics.on_screen_s),
        "physical": {
            "total_distance_m": _round(kin.total_distance_m),
            "distance_per_min_m": _round(kin.distance_per_min),
            "distance_by_zone_m": {k: _round(v) for k, v in kin.distance_by_zone_m.items()},
            "high_intensity_distance_m": _round(kin.high_intensity_distance_m),
            "top_speed_kmh": _round(kin.top_speed_kmh),
            "avg_speed_kmh": _round(kin.avg_speed_kmh),
            "sprints": len(kin.sprints),
            "sprint_details": [
                {"start_s": _round(s.start_s), "end_s": _round(s.end_s), "peak_kmh": _round(s.peak_kmh), "distance_m": _round(s.distance_m)}
                for s in kin.sprints
            ],
            "accelerations": kin.accelerations,
            "decelerations": kin.decelerations,
            "time_tracked_s": _round(kin.time_tracked_s),
        },
        "pose": {
            "cadence_steps_per_min": _round(pose.cadence_spm),
            "trunk_lean_deg": _round(pose.trunk_lean_deg),
            "keypoint_visibility": _round(pose.keypoint_visibility, 2),
        },
        "ball": {"control_time_s": _round(player.possession_s), "touches": player.touches},
        "events": player.counts.as_dict() if player.counts else None,
        "pass_accuracy": _round(player.counts.pass_accuracy, 3) if player.counts else None,
        "ratings": {
            **player.ratings.attributes,
            "overall": player.ratings.overall,
            "position": player.ratings.position,
            "estimated": sorted(player.ratings.estimated),
        },
        "assessment": player.assessment.model_dump(mode="json") if player.assessment else None,
    }


def report_to_dict(report: MatchReport) -> dict[str, Any]:
    team = report.focus_team
    return {
        "video": {
            "path": str(report.video.path),
            "fps": report.video.fps,
            "frames": report.video.frame_count,
            "frame_stride": report.video.frame_stride,
            "duration_s": _round(report.video.frame_count / report.video.fps),
        },
        "target": {
            "mode": "player" if report.target.is_player_mode else "team",
            "team_id": report.target.team_id,
            "player_id": report.target.player_id,
            "jersey_number": report.target.jersey_number,
            "label": report.target.label,
        },
        "geometry_mode": report.geometry_mode,
        "gemini_status": report.gemini_status,
        "team": {
            "color": team.color_name,
            "opponent_color": report.opponent_color,
            "possession_share": _round(team.possession_share, 3),
            "events": team.counts.as_dict() if team.counts else None,
            "players": [player_to_dict(p) for p in team.players],
        },
        "focus_player": player_to_dict(report.focus_player) if report.focus_player else None,
        "gemini": report.gemini.model_dump(mode="json") if report.gemini else None,
        "caveats": report.caveats,
    }
