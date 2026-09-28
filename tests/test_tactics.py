from survivors_bot.tactics import BossEvidence, BossState, BossTracker, Threat, choose_evasive_direction


def test_evasive_policy_ignores_distant_threats_and_avoids_near_ones():
    assert choose_evasive_direction([Threat(0.95, 0.05)]) is None
    move = choose_evasive_direction([Threat(0.58, 0.5, kind="projectile")])
    assert move is not None
    # Threat is to the right, so the chosen escape should not point right.
    assert move[0] < 0


def test_boss_requires_persistent_independent_visual_evidence():
    tracker = BossTracker(enter_frames=2, clear_frames=3)
    timer_only = BossEvidence(timer_hint=1.0)
    assert tracker.update(timer_only) == BossState.SUSPECTED
    assert tracker.update(BossEvidence()) == BossState.SUSPECTED
    assert tracker.update(BossEvidence()) == BossState.NORMAL

    visual = BossEvidence(boss_sprite=0.95, health_bar=0.9)
    assert tracker.update(visual) == BossState.SUSPECTED
    assert tracker.update(visual) == BossState.ACTIVE
    assert tracker.update(BossEvidence()) == BossState.SUSPECTED
