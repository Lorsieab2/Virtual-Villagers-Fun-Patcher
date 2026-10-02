"""The Lost Children: Pick Gong of Wonder Outcome -- the Gong's own rolls.

A gong use is a villager finishing the action "Ringing the Gong of Wonder"
(action 66; the action-completion dispatcher 0x461B10, case 0x461B32) once
its one-day cooldown (village +0x2EAC8) has passed: the call at 0x461B8E
then runs the outcome routine 0x44E8A0 (its only caller).  The routine
picks a tier (A 5%, B 25% of the rest -- both only once a tier-C result
has set village byte +0x2E910 -- else C) and an entry of that tier's
table, then any amount, victim or sickness rolls.  Traced in the stock
executable; each control cites the code in its "evidence".  GENERATED from
the research table and reviewed.
"""
# flake8: noqa

USE_CALLS = [0x461B8E]

CONTROLS = [
    {
        'id': 'result',
        'label': 'What the Gong does',
        'branch': None,
        'phase': 'apply',
        'scope_call': 0x461B8E,
        'kind': 'enum',
        'options': [
            {
                'label': "Grants vision (string 0x114; 'vision' timer = now+30 s)",
                'force': [
                    [0x44E8A8, 0],
                    [0x44E8CF, 0],
                ],
                'condition': 'needs the tiers unlocked: village byte [[this+0xE574D4]+0x2E910] != 0 (checked at 0x44E8C1 / 0x44EBD7).  Only a tier-C result sets it (0x44EFDB) and nothing clears it, so the first gong use (with the flag 0) is always tier C.  No save/load code references the byte by displacement; if it is not saved it is 0 again after each launch.  Read it live before offering this option.',
                'cond': 'vv2_gong_tiers',
            },
            {
                'label': 'Grants food: +1000 food, plant store = 800, coconut trees = 30 (+30 with Coconuts Fix)',
                'force': [
                    [0x44E8A8, 0],
                    [0x44E8CF, 1],
                ],
                'condition': 'needs the tiers unlocked: village byte [[this+0xE574D4]+0x2E910] != 0 (checked at 0x44E8C1 / 0x44EBD7).  Only a tier-C result sets it (0x44EFDB) and nothing clears it, so the first gong use (with the flag 0) is always tier C.  No save/load code references the byte by displacement; if it is not saved it is 0 again after each launch.  Read it live before offering this option.',
                'cond': 'vv2_gong_tiers',
            },
            {
                'label': "Grants technology: +20000..59999 tech (see 'Technology gained (big)')",
                'force': [
                    [0x44E8A8, 0],
                    [0x44E8CF, 2],
                ],
                'condition': 'needs the tiers unlocked: village byte [[this+0xE574D4]+0x2E910] != 0 (checked at 0x44E8C1 / 0x44EBD7).  Only a tier-C result sets it (0x44EFDB) and nothing clears it, so the first gong use (with the flag 0) is always tier C.  No save/load code references the byte by displacement; if it is not saved it is 0 again after each launch.  Read it live before offering this option.',
                'cond': 'vv2_gong_tiers',
            },
            {
                'label': 'Takes food: food, plant store and coconut trees all set to 0',
                'force': [
                    [0x44E8A8, 0],
                    [0x44E8CF, 3],
                ],
                'condition': 'needs the tiers unlocked: village byte [[this+0xE574D4]+0x2E910] != 0 (checked at 0x44E8C1 / 0x44EBD7).  Only a tier-C result sets it (0x44EFDB) and nothing clears it, so the first gong use (with the flag 0) is always tier C.  No save/load code references the byte by displacement; if it is not saved it is 0 again after each launch.  Read it live before offering this option.',
                'cond': 'vv2_gong_tiers',
            },
            {
                'label': 'Grants life: every woman aged 18-49, not pregnant, gets full health, is cured and becomes pregnant (population cap permitting)',
                'force': [
                    [0x44E8A8, 0],
                    [0x44E8CF, 4],
                ],
                'condition': 'needs the tiers unlocked: village byte [[this+0xE574D4]+0x2E910] != 0 (checked at 0x44E8C1 / 0x44EBD7).  Only a tier-C result sets it (0x44EFDB) and nothing clears it, so the first gong use (with the flag 0) is always tier C.  No save/load code references the byte by displacement; if it is not saved it is 0 again after each launch.  Read it live before offering this option.',
                'cond': 'vv2_gong_tiers',
            },
            {
                'label': 'Takes life: the villager who rang it dies (health 0)',
                'force': [
                    [0x44E8A8, 0],
                    [0x44E8CF, 5],
                ],
                'condition': "needs the tiers unlocked: village byte [[this+0xE574D4]+0x2E910] != 0 (checked at 0x44E8C1 / 0x44EBD7).  Only a tier-C result sets it (0x44EFDB) and nothing clears it, so the first gong use (with the flag 0) is always tier C.  No save/load code references the byte by displacement; if it is not saved it is 0 again after each launch.  Read it live before offering this option.; and the villager who rang the gong = 0x44B440: first record (index order) that is active, health > 0, age +0x530 > 0x118 (adult) and whose task text +0x4FC equals string 0x10C 'Ringing the Gong of Wonder'; if none (e.g. a child rang it) the message still shows but nothing else happens (cmp eax,-1 -> 0x44F448)",
                'cond': 'vv2_gong_tiers',
            },
            {
                'label': "Takes health: each villager may fall sick (30%, see 'Who falls sick')",
                'force': [
                    [0x44E8A8, 0x63],
                    [0x44EBC0, 0],
                    [0x44EBE5, 0],
                ],
                'condition': 'needs the tiers unlocked: village byte [[this+0xE574D4]+0x2E910] != 0 (checked at 0x44E8C1 / 0x44EBD7).  Only a tier-C result sets it (0x44EFDB) and nothing clears it, so the first gong use (with the flag 0) is always tier C.  No save/load code references the byte by displacement; if it is not saved it is 0 again after each launch.  Read it live before offering this option.',
                'cond': 'vv2_gong_tiers',
            },
            {
                'label': 'Grants luck (string 0x116; luck timer = now+60 s)',
                'force': [
                    [0x44E8A8, 0x63],
                    [0x44EBC0, 0],
                    [0x44EBE5, 1],
                ],
                'condition': 'needs the tiers unlocked: village byte [[this+0xE574D4]+0x2E910] != 0 (checked at 0x44E8C1 / 0x44EBD7).  Only a tier-C result sets it (0x44EFDB) and nothing clears it, so the first gong use (with the flag 0) is always tier C.  No save/load code references the byte by displacement; if it is not saved it is 0 again after each launch.  Read it live before offering this option.',
                'cond': 'vv2_gong_tiers',
            },
            {
                'label': "Grants technology: +10000..29999 tech (see 'Technology gained (medium)')",
                'force': [
                    [0x44E8A8, 0x63],
                    [0x44EBC0, 0],
                    [0x44EBE5, 2],
                ],
                'condition': 'needs the tiers unlocked: village byte [[this+0xE574D4]+0x2E910] != 0 (checked at 0x44E8C1 / 0x44EBD7).  Only a tier-C result sets it (0x44EFDB) and nothing clears it, so the first gong use (with the flag 0) is always tier C.  No save/load code references the byte by displacement; if it is not saved it is 0 again after each launch.  Read it live before offering this option.',
                'cond': 'vv2_gong_tiers',
            },
            {
                'label': "Grants food: +1000..2999 food (see 'Food gained (big)')",
                'force': [
                    [0x44E8A8, 0x63],
                    [0x44EBC0, 0],
                    [0x44EBE5, 3],
                ],
                'condition': 'needs the tiers unlocked: village byte [[this+0xE574D4]+0x2E910] != 0 (checked at 0x44E8C1 / 0x44EBD7).  Only a tier-C result sets it (0x44EFDB) and nothing clears it, so the first gong use (with the flag 0) is always tier C.  No save/load code references the byte by displacement; if it is not saved it is 0 again after each launch.  Read it live before offering this option.',
                'cond': 'vv2_gong_tiers',
            },
            {
                'label': 'Takes health: the villager who rang it loses 90 health (to 0 at most)',
                'force': [
                    [0x44E8A8, 0x63],
                    [0x44EBC0, 0],
                    [0x44EBE5, 4],
                ],
                'condition': "needs the tiers unlocked: village byte [[this+0xE574D4]+0x2E910] != 0 (checked at 0x44E8C1 / 0x44EBD7).  Only a tier-C result sets it (0x44EFDB) and nothing clears it, so the first gong use (with the flag 0) is always tier C.  No save/load code references the byte by displacement; if it is not saved it is 0 again after each launch.  Read it live before offering this option.; and the villager who rang the gong = 0x44B440: first record (index order) that is active, health > 0, age +0x530 > 0x118 (adult) and whose task text +0x4FC equals string 0x10C 'Ringing the Gong of Wonder'; if none (e.g. a child rang it) the message still shows but nothing else happens (cmp eax,-1 -> 0x44F448)",
                'cond': 'vv2_gong_tiers',
            },
            {
                'label': 'Takes food: the plant store (village +0x2EAD8) set to 0',
                'force': [
                    [0x44E8A8, 0x63],
                    [0x44EBC0, 0],
                    [0x44EBE5, 5],
                ],
                'condition': 'needs the tiers unlocked: village byte [[this+0xE574D4]+0x2E910] != 0 (checked at 0x44E8C1 / 0x44EBD7).  Only a tier-C result sets it (0x44EFDB) and nothing clears it, so the first gong use (with the flag 0) is always tier C.  No save/load code references the byte by displacement; if it is not saved it is 0 again after each launch.  Read it live before offering this option.',
                'cond': 'vv2_gong_tiers',
            },
            {
                'label': 'Takes food: coconut trees set to 0',
                'force': [
                    [0x44E8A8, 0x63],
                    [0x44EBC0, 0],
                    [0x44EBE5, 6],
                ],
                'condition': 'needs the tiers unlocked: village byte [[this+0xE574D4]+0x2E910] != 0 (checked at 0x44E8C1 / 0x44EBD7).  Only a tier-C result sets it (0x44EFDB) and nothing clears it, so the first gong use (with the flag 0) is always tier C.  No save/load code references the byte by displacement; if it is not saved it is 0 again after each launch.  Read it live before offering this option.',
                'cond': 'vv2_gong_tiers',
            },
            {
                'label': 'Takes youth: villager slot 6 gets age value 1001 (stock writes record 6, NOT the ringer)',
                'force': [
                    [0x44E8A8, 0x63],
                    [0x44EBC0, 0],
                    [0x44EBE5, 7],
                ],
                'condition': 'needs the tiers unlocked: village byte [[this+0xE574D4]+0x2E910] != 0 (checked at 0x44E8C1 / 0x44EBD7).  Only a tier-C result sets it (0x44EFDB) and nothing clears it, so the first gong use (with the flag 0) is always tier C.  No save/load code references the byte by displacement; if it is not saved it is 0 again after each launch.  Read it live before offering this option.; and a ringer must exist (0x44EF36-0x44EF3E)',
                'cond': 'vv2_gong_tiers',
            },
            {
                'label': 'Grants youth: villager slot 15 gets age value 100 (stock writes record 15, NOT the ringer)',
                'force': [
                    [0x44E8A8, 0x63],
                    [0x44EBC0, 0],
                    [0x44EBE5, 8],
                ],
                'condition': 'needs the tiers unlocked: village byte [[this+0xE574D4]+0x2E910] != 0 (checked at 0x44E8C1 / 0x44EBD7).  Only a tier-C result sets it (0x44EFDB) and nothing clears it, so the first gong use (with the flag 0) is always tier C.  No save/load code references the byte by displacement; if it is not saved it is 0 again after each launch.  Read it live before offering this option.; and a ringer must exist (0x44EFA9-0x44EFB1)',
                'cond': 'vv2_gong_tiers',
            },
            {
                'label': 'Grants health: every villager healed to 100 and cured',
                'force': [
                    [0x44E8A8, 0x63],
                    [0x44EBC0, 0x63],
                    [0x44EFE4, 0],
                ],
                'condition': None,
            },
            {
                'label': "Grants food: +200..999 food (see 'Food gained (small)')",
                'force': [
                    [0x44E8A8, 0x63],
                    [0x44EBC0, 0x63],
                    [0x44EFE4, 1],
                ],
                'condition': None,
            },
            {
                'label': 'Grants food: plant store (village +0x2EAD8) set to 800',
                'force': [
                    [0x44E8A8, 0x63],
                    [0x44EBC0, 0x63],
                    [0x44EFE4, 2],
                ],
                'condition': None,
            },
            {
                'label': 'Grants food: coconut trees set to 30 (+30 with Coconuts Fix)',
                'force': [
                    [0x44E8A8, 0x63],
                    [0x44EBC0, 0x63],
                    [0x44EFE4, 3],
                ],
                'condition': None,
            },
            {
                'label': "Grants technology: +3000..12999 tech (see 'Technology gained (small)')",
                'force': [
                    [0x44E8A8, 0x63],
                    [0x44EBC0, 0x63],
                    [0x44EFE4, 4],
                ],
                'condition': None,
            },
            {
                'label': "Takes technology: -3000..12999 tech (see 'Technology lost')",
                'force': [
                    [0x44E8A8, 0x63],
                    [0x44EBC0, 0x63],
                    [0x44EFE4, 5],
                ],
                'condition': None,
            },
            {
                'label': "Takes health: each villager may fall sick (15%, see 'Who falls sick')",
                'force': [
                    [0x44E8A8, 0x63],
                    [0x44EBC0, 0x63],
                    [0x44EFE4, 6],
                ],
                'condition': None,
            },
            {
                'label': "Grants wisdom: one skill of the villager who rang it set to 100 (see 'Skill')",
                'force': [
                    [0x44E8A8, 0x63],
                    [0x44EBC0, 0x63],
                    [0x44EFE4, 7],
                ],
                'condition': "the villager who rang the gong = 0x44B440: first record (index order) that is active, health > 0, age +0x530 > 0x118 (adult) and whose task text +0x4FC equals string 0x10C 'Ringing the Gong of Wonder'; if none (e.g. a child rang it) the message still shows but nothing else happens (cmp eax,-1 -> 0x44F448)",
            },
        ],
        'evidence': 'Gates: 0x44E8A4 push 0x64 / E8 at 0x44E8A8, cmp eax,5 jge 0x44EBBE; flag 0x44E8C1.  0x44EBBE push 0x64 / E8 at 0x44EBC0, cmp eax,0x19 jge 0x44EFCD; flag 0x44EBD7.  Tier A: push 6 / E8 0x44E8CF, ja 0x44F448, jmp [0x44F450+eax*4] = 44E8E7 (0x114 vision, [v+0x30464]=now+0x1E), 44E94E (0x112: 0x4262B0(1000) at 0x44E9BE, [v+0x2EAD8]=0x320 0x44E999, [v+0x2EACC]=0x1E 0x44E9A9), 44E9C8 (0x113 tech), 44EA37 (0x11B: +0x2EAA4, +0x2EAD8, +0x2EACC = 0 at 0x44EA82/8E/9D), 44EAA5 (0x115 life loop 0x44EAF5-0x44EB50: active, age 0x168..0x3E7, health>0, sex==2, +0x540==0 -> health=100, sick=0, 0x44B980), 44EB57 (0x11E: ringer health +0x52C = 0 at 0x44EBB3).  Tier B: push 9 / E8 0x44EBE5, jmp [0x44F468+eax*4] = 44EBFD (0x11A loop), 44EC85 (0x116, [v+0x2EAE0]=now+0x3C), 44ECE9 (0x113), 44ED57 (0x112), 44EDBE (0x11A ringer health -0x5A, clamp 0 at 0x44EE2D), 44EE3A (0x11B +0x2EAD8=0), 44EE95 (0x11B +0x2EACC=0), 44EEEB (0x11D: [this+0x56078] and [this+0x5607C] = 0x3E9 = record 6 +0x530/+0x534; ringer index in eax is overwritten at 0x44EF44), 44EF5A (0x117: [this+0xD6964]/[+0xD6968] = 0x64 = record 15 +0x530/+0x534).  Tier C: push 9 / E8 0x44EFE4, jmp [0x44F48C+eax*4] = 44EFFC (0x119: all active living +0x558==0 -> health 100, sick 0), 44F077 (0x112 food), 44F0DE (0x112 +0x2EAD8=0x320), 44F138 (0x112 +0x2EACC=0x1E at 0x44F18C), 44F198 (0x113 tech), 44F207 (0x11C tech loss), 44F279 (0x11A loop), 44F305 and 44F376 (both 0x118 wisdom, identical -> one option, value 7).',
    },
    {
        'id': 'tech_big',
        'label': "Technology gained (big, 'Grants technology' tier A)",
        'branch': None,
        'phase': 'apply',
        'scope_call': 0x461B8E,
        'kind': 'amount',
        'site': 0x44EA19,
        'bound': 0x9C40,
        'base': 0x4E20,
        'step': 1,
        'unit': 'tech',
        'condition': "only with result 'Grants technology: +20000..59999'",
        'evidence': '0x44EA14 push 0x9C40; E8 0x44EA19; add eax,0x4E20 (0x44EA27); 0x426290 at 0x44EA2D. No clamp.',
    },
    {
        'id': 'tech_medium',
        'label': 'Technology gained (medium, tier B)',
        'branch': None,
        'phase': 'apply',
        'scope_call': 0x461B8E,
        'kind': 'amount',
        'site': 0x44ED39,
        'bound': 0x4E20,
        'base': 0x2710,
        'step': 1,
        'unit': 'tech',
        'condition': "only with result 'Grants technology: +10000..29999'",
        'evidence': '0x44ED34 push 0x4E20; E8 0x44ED39; add eax,0x2710; 0x426290 at 0x44ED4D. No clamp.',
    },
    {
        'id': 'tech_small',
        'label': 'Technology gained (small, tier C)',
        'branch': None,
        'phase': 'apply',
        'scope_call': 0x461B8E,
        'kind': 'amount',
        'site': 0x44F1E9,
        'bound': 0x2710,
        'base': 0xBB8,
        'step': 1,
        'unit': 'tech',
        'condition': "only with result 'Grants technology: +3000..12999'",
        'evidence': '0x44F1E4 push 0x2710; E8 0x44F1E9; add eax,0xBB8; 0x426290 at 0x44F1FD. No clamp.',
    },
    {
        'id': 'tech_lost',
        'label': 'Technology lost (tier C)',
        'branch': None,
        'phase': 'apply',
        'scope_call': 0x461B8E,
        'kind': 'amount',
        'site': 0x44F257,
        'bound': 0x2710,
        'base': 0xBB8,
        'step': 1,
        'unit': 'tech lost',
        'condition': "only with result 'Takes technology'",
        'evidence': '0x44F252 push 0x2710; E8 0x44F257; ecx = -0xBB8 - eax (0x44F25F-0x44F264); [v+0x2EADC] += ecx (0x44F26F).  Not clamped: stock can drive tech below 0.',
    },
    {
        'id': 'food_big',
        'label': 'Food gained (big, tier B)',
        'branch': None,
        'phase': 'apply',
        'scope_call': 0x461B8E,
        'kind': 'amount',
        'site': 0x44EDA0,
        'bound': 0x7D0,
        'base': 1000,
        'step': 1,
        'unit': 'food',
        'condition': "only with result 'Grants food: +1000..2999'",
        'evidence': '0x44ED9B push 0x7D0; E8 0x44EDA0; add eax,0x3E8; 0x4262B0 at 0x44EDB4. No clamp.',
    },
    {
        'id': 'food_small',
        'label': 'Food gained (small, tier C)',
        'branch': None,
        'phase': 'apply',
        'scope_call': 0x461B8E,
        'kind': 'amount',
        'site': 0x44F0C0,
        'bound': 800,
        'base': 200,
        'step': 1,
        'unit': 'food',
        'condition': "only with result 'Grants food: +200..999'",
        'evidence': '0x44F0BB push 0x320; E8 0x44F0C0; add eax,0xC8; 0x4262B0 at 0x44F0D4. No clamp.',
    },
    {
        'id': 'sick_b',
        'label': "Who falls sick ('Takes health', 30%, tier B)",
        'branch': None,
        'phase': 'apply',
        'scope_call': 0x461B8E,
        'kind': 'loop',
        'site': 0x44EC67,
        'bound': 100,
        'everyone': 0,
        'nobody': 99,
        'record': {
            'reg': 'esi',
            'disp': -0x52C,
        },
        'what': 'falls sick (+0x53C = 1)',
        'warn_everyone': None,
        'condition': "only with result 'Takes health: each villager may fall sick (30%)'",
        'evidence': '0x44EC44 esi = this+0x52C, stride 0xE48C, 256 records (0x44EC4A); skip if +0x30 == 0 (0x44EC54), health +0x52C <= 0 (0x44EC5C) or byte +0x558 != 0 (0x44EC60); push 0x64 / E8 0x44EC67; cmp eax,0x1E jge -> skip; else [esi+0x10] (+0x53C) = 1.  ESI at the call = record + 0x52C.',
    },
    {
        'id': 'sick_c',
        'label': "Who falls sick ('Takes health', 15%, tier C)",
        'branch': None,
        'phase': 'apply',
        'scope_call': 0x461B8E,
        'kind': 'loop',
        'site': 0x44F2E7,
        'bound': 100,
        'everyone': 0,
        'nobody': 99,
        'record': {
            'reg': 'esi',
            'disp': -0x52C,
        },
        'what': 'falls sick (+0x53C = 1)',
        'warn_everyone': None,
        'condition': "only with result 'Takes health: each villager may fall sick (15%)'",
        'evidence': '0x44F2C4 esi = this+0x52C; same filters 0x44F2D4/0x44F2DC/0x44F2E0; push 0x64 / E8 0x44F2E7; cmp eax,0xF jge -> skip; else +0x53C = 1 (0x44F2F4).',
    },
    {
        'id': 'skill',
        'label': "Skill raised to 100 ('Grants wisdom')",
        'branch': None,
        'phase': 'apply',
        'scope_call': 0x461B8E,
        'kind': 'enum',
        'condition': "only with result 'Grants wisdom'; the villager who rang the gong = 0x44B440: first record (index order) that is active, health > 0, age +0x530 > 0x118 (adult) and whose task text +0x4FC equals string 0x10C 'Ringing the Gong of Wonder'; if none (e.g. a child rang it) the message still shows but nothing else happens (cmp eax,-1 -> 0x44F448)",
        'options': [
            {
                'label': 'Parenting',
                'force': [
                    [0x44F35E, 0],
                    [0x44F3CB, 0],
                ],
                'condition': None,
            },
            {
                'label': 'Building',
                'force': [
                    [0x44F35E, 1],
                    [0x44F3CB, 1],
                ],
                'condition': None,
            },
            {
                'label': 'Healing',
                'force': [
                    [0x44F35E, 2],
                    [0x44F3CB, 2],
                ],
                'condition': None,
            },
            {
                'label': 'Research',
                'force': [
                    [0x44F35E, 3],
                    [0x44F3CB, 3],
                ],
                'condition': None,
            },
            {
                'label': 'Farming',
                'force': [
                    [0x44F35E, 4],
                    [0x44F3CB, 4],
                ],
                'condition': None,
            },
        ],
        'evidence': 'Entry 7: ringer via 0x44F34C, -1 -> end; push 5 / E8 0x44F35E; jmp [0x44F4B0+eax*4].  Entry 8: ringer 0x44F3BD; push 5 / E8 0x44F3CB; jmp [0x44F4C4+eax*4].  Both tables = 44F3DF (+0x7E4 parenting = 100), 44F3F5 (+0x7E8 building), 44F40B (+0x7F0 healing), 44F421 (+0x7F4 research), 44F437 (+0x7EC farming); record = this + ringer*0xE48C.',
    },
    {
        'id': 'babies',
        'label': "Babies per pregnancy ('Grants life')",
        'branch': None,
        'phase': 'apply',
        'scope_call': 0x44EB3E,
        'kind': 'enum',
        'condition': "only with result 'Grants life'; twins/triplets rolls run only when the village breeding level [v+0x2EA8C] == 3 (0x44BA6A / 0x44BA9E); forced for every woman made pregnant in this use",
        'options': [
            {
                'label': 'One baby',
                'force': [
                    [0x44BA75, 0x63],
                ],
                'condition': None,
            },
            {
                'label': 'Twins',
                'force': [
                    [0x44BA75, 0],
                    [0x44BAA9, 0x63],
                ],
                'condition': '[v+0x2EA8C] == 3',
                'cond': 'vv2_breeding_mastered',
            },
            {
                'label': 'Triplets',
                'force': [
                    [0x44BA75, 0],
                    [0x44BAA9, 0],
                ],
                'condition': '[v+0x2EA8C] == 3',
                'cond': 'vv2_breeding_mastered',
            },
        ],
        'evidence': '0x44EB3E E8 -> 0x44B980 (shared pregnancy routine; other callers 0x422006, 0x44F8F0, 0x44F930, 0x464A38, 0x464C4D -> must be scoped to 0x44EB3E).  0x44B980: cap check 0x44B310 (no rand), +0x44 = 0x1A, babies +0x540; push 0x64 / E8 0x44BA75, cmp 7 jge -> single; else +0x544 = 2, then push 0x64 / E8 0x44BAA9, cmp 0x19 jge -> twins; else +0x544 = 3 (triplets).',
    },
]

CONDITIONS = "A gong use = a villager completing action 66 'Ringing the Gong of Wonder' (player drop or own choice; both end in the action-completion dispatcher 0x461B10, case 0x461B32) while the cooldown has expired.  Tier A/B results need village byte +0x2E910 != 0 (set only by a tier-C result, so never on the first use).  Ringer-based results (takes life, ringer -90 health, wisdom, and the two youth writes) need an adult (age > 0x118) whose task text is still 'Ringing the Gong of Wonder' (0x44B440); otherwise only the message shows.  'Grants life' affects only women aged 0x168..0x3E7 (18-49), alive, not already pregnant, and stops making them pregnant once the population cap (0x44B310) is reached.  The sickness loops and 'grants health' skip records with byte +0x558 set."

COOLDOWN = "village dword +0x2EAC8 = next allowed time.  0x461B3A-0x461B45: if [v+0x2EAC8] >= now (0x403200) the ring does nothing (0x44E8A0 not called).  Otherwise 0x461B5D sets it to now + 86400 s ('about a full day', string 0x1C0, shown once via byte +0x1F1).  Reset to 0 elsewhere at 0x4251FE (init) and 0x4639F6, 0x463BC7, 0x463D43, 0x463EF4.  An armed pick therefore waits for the next real use; disarm on return from 0x461B8E."

OMITTED = [
    "0x44EB32 rand(50) in 'Grants life': passed as arg2 of 0x44B980 and stored at the mother's +0x5EC (0x44BA1A); no code reads +0x5EC by displacement (only writes at 0x424FD8, 0x44BA1A, 0x44C992, 0x44CF86, 0x44D2CD), so no traced effect -> not offered (uncertain: could be read through a whole-record copy).",
    'Jump-table default branches (ja 0x44F448 after cmp 5 / cmp 8 / cmp 4) are dead: rand(6)/rand(9)/rand(5) can never exceed the bound.',
    "Tier-C entries 7 and 8 (0x44F305 / 0x44F376) are byte-identical 'Grants wisdom' paths -> one option.",
    'No other developer-dead outcomes: every table entry of all three tiers is reachable in stock (A/B after the first tier-C ring).',
    "Stock defect, offered as-is (it is what stock produces): 'Takes youth' / 'Grants youth' write fixed records 6 and 15 instead of the ringer (0x44EF44-0x44EF50, 0x44EFB7-0x44EFC3).",
]

COSMETIC = [
    '0x44E914/0x44E923, 0x44E962/0x44E96E, 0x44E9E2/0x44E9EE, 0x44EA4A/0x44EA56, 0x44EAB8/0x44EAC7, 0x44EB6A/0x44EB76, 0x44EC12/0x44EC1E, 0x44EC98/0x44ECA4, 0x44ED02/0x44ED0E, 0x44ED6A/0x44ED76, 0x44EDD2/0x44EDDE, 0x44EE52/0x44EE5E, 0x44EEA8/0x44EEB4, 0x44EF02/0x44EF0E, 0x44EF72/0x44EF81, 0x44F012/0x44F01E, 0x44F08A/0x44F096, 0x44F0F2/0x44F0FE, 0x44F152/0x44F15E, 0x44F1B2/0x44F1BE, 0x44F21A/0x44F226, 0x44F292/0x44F29E, 0x44F318/0x44F324, 0x44F389/0x44F395: sparkle particle positions (x/y) passed to 0x4239D0, 6-20 per outcome.',
    '0x461BBC (and 0x4599C0/0x4599D3/0x4599ED in 0x459980): after the outcome, which villagers walk over to watch the gong and where they stand -- outside 0x44E8A0, not an outcome.',
]

COCONUTS_FIX = {
    'patch_file_offsets': [0x4E9A9, 0x4F18C],
    'patch_vas': [0x44E9A9, 0x44F18C],
    'patch_len': 10,
    'normal_path': "tier A entry 1 (0x44E94E): food +1000, plant store 800, coconuts 30 -> option 'Grants food: +1000 food, plant store = 800, coconut trees = 30'",
    'alternate_path': "tier C entry 3 (0x44F138): coconuts 30 only -> option 'Grants food: coconut trees set to 30'",
    'overlap': 'none (checked: no listed site, scope_call or use_call byte range intersects either 10-byte patch)',
}
