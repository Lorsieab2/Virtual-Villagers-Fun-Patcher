"""Pick Island Event outcomes: New Believers (VV5).

Traced in the stock executable (each control's "evidence" cites the code);
see scripts/story_island_outcomes.py for the format.  GENERATED from the
research tables and reviewed; edit with care: every site is re-checked
against every render by scripts/build_story_cheat_upgrades_features.py.
"""
# flake8: noqa

GAME = 'vv5'

CONTROLS = {
    5: [
        {
            'id': 'subject',
            'label': 'Which villager sees the vision',
            'branch': None,
            'phase': 'select',
            'scope_call': 0x414BB4,
            'kind': 'victim',
            'site': 0x471A25,
            'candidates': {
                'base': {
                    'reg': 'esp',
                    'disp': 0x18,
                },
                'elem': 'index',
                'elem_disp': 0,
                'size': 4,
            },
            'filter': 'record in use (0x466170(0) at 0x4718A8), health [rec+0x1C40] > 0 (0x4718B5), not busy with activity 0xC..0x11 at [rec+0x1CFC] (a14=0, 0x471994..0x4719B6); believers only ([rec+0x1CEC]==0; a11=0,a13=0 -> 0x4719C2..0x4719CD); any age, any sex, pregnant and sick allowed',
            'evidence': 'Picker 0x471870 (thiscall ecx=0x554148, 14 args, ret 0x38): loops i=0..0x95 over records 0x554190+i*0x2F44 (esi=rec+0x1B8C), appends qualifying i to a stack list (0x4719E2 mov [esp+ebx*4+0x14],edi), then 0x471A24 push ebx(count) / 0x471A25 call rand / 0x471A2A mov ecx,[esp+eax*4+0x18] / 0x471A3E lea eax,[ecx*0x2F44+edx+0x48] -> returns record base. So at the CALL (after push ebx) the candidate list is dword record INDEXES at esp+0x18, bound = count (variable, >=1 because 0x471A13 returns 0 when empty). m1 0x414b90 calls the picker at 0x414bb4 and stores the result at [esi+4]. The m1 is called by the selector 0x418870 on every pass (phase select).',
            'note': 'Stored at [event+4] by m1 0x414b90; apply 0x414BD0 gives that villager the faith (0x414BE4 FAITH_ADD). m1 does `mov esi,ecx` before the picker call and the picker saves esi at 0x47187F, so at the site dword [esp+8] = the event object evaluating its condition (use it to tell slots apart when several slots share this m1). This m1 is shared by slots 5, 12, 35, 43, 45; the same scope_call evaluates their subjects too.',
        },
        {
            'id': 'faith',
            'label': 'Faith gained',
            'branch': None,
            'phase': 'apply',
            'scope_call': None,
            'kind': 'amount',
            'site': 0x414BD5,
            'bound': 20,
            'base': 20,
            'step': 1,
            'unit': 'faith (20..39)',
            'evidence': "0x414BD1 push 0x14; 0x414BD5 call rand; 0x414BE0 add eax,0x14; 0x414BE4 0x468020 FAITH_ADD on [event+4] -> 0x467F90 SET_FAITH(old+v,1) clamps to <=100 (0x467FE4). Apply 0x414BD0 is referenced only by slot 5's vtable.",
        },
    ],
    6: [
        {
            'id': 'weather_length',
            'label': 'How long the weather lasts',
            'branch': None,
            'phase': 'apply',
            'scope_call': 0x414C37,
            'kind': 'amount',
            'site': 0x4771C5,
            'bound': 180,
            'base': 180,
            'step': 1,
            'unit': 'game-clock units of 0x41ED40 after the event (180..359)',
            'evidence': "0x477060(type=4, 0) on 0x718EA0: [esi]=4, jump table 0x47721C[4] = 0x477119; then 0x4771A6 type != 0 -> edi=0xB4, eax=0x168 (0x4771B7/0x4771BC), bound = 0x168-0xB4 = 180 pushed at 0x4771C4, 0x4771C5 call rand, 0x4771D9 ebx+=0xB4, 0x4771DF eax = clock 0x41ED40() + ebx, 0x4771E3 [esi+8] = end time. 0x477060 has 12 callers (natural weather scheduler 0x477298/0x477563/... too), so it is scoped by this event's own call. Scope: apply calls 0x477060(4,0) at 0x414c37.",
            'note': "The event's food gained part is fixed (no roll).",
        },
    ],
    7: [
        {
            'id': 'weather_length',
            'label': 'How long the weather lasts',
            'branch': None,
            'phase': 'apply',
            'scope_call': 0x414C9C,
            'kind': 'amount',
            'site': 0x4771C5,
            'bound': 180,
            'base': 180,
            'step': 1,
            'unit': 'game-clock units of 0x41ED40 after the event (180..359)',
            'evidence': "0x477060(type=4, 0) on 0x718EA0: [esi]=4, jump table 0x47721C[4] = 0x477119; then 0x4771A6 type != 0 -> edi=0xB4, eax=0x168 (0x4771B7/0x4771BC), bound = 0x168-0xB4 = 180 pushed at 0x4771C4, 0x4771C5 call rand, 0x4771D9 ebx+=0xB4, 0x4771DF eax = clock 0x41ED40() + ebx, 0x4771E3 [esi+8] = end time. 0x477060 has 12 callers (natural weather scheduler 0x477298/0x477563/... too), so it is scoped by this event's own call. Scope: apply calls 0x477060(4,0) at 0x414c9c.",
            'note': "The event's food lost part is fixed (no roll).",
        },
    ],
    11: [
        {
            'id': 'subject',
            'label': 'Who has the bed bug bites',
            'branch': None,
            'phase': 'select',
            'scope_call': 0x415664,
            'kind': 'victim',
            'site': 0x471A25,
            'candidates': {
                'base': {
                    'reg': 'esp',
                    'disp': 0x18,
                },
                'elem': 'index',
                'elem_disp': 0,
                'size': 4,
            },
            'filter': 'record in use (0x466170(0) at 0x4718A8), health [rec+0x1C40] > 0 (0x4718B5), not busy with activity 0xC..0x11 at [rec+0x1CFC] (a14=0, 0x471994..0x4719B6); believers only ([rec+0x1CEC]==0; a11=0,a13=0 -> 0x4719C2..0x4719CD); not pregnant/nursing ([rec+0x1C4C]==0; a4=0 -> 0x471909); any age, any sex, sick allowed',
            'evidence': 'Picker 0x471870 (thiscall ecx=0x554148, 14 args, ret 0x38): loops i=0..0x95 over records 0x554190+i*0x2F44 (esi=rec+0x1B8C), appends qualifying i to a stack list (0x4719E2 mov [esp+ebx*4+0x14],edi), then 0x471A24 push ebx(count) / 0x471A25 call rand / 0x471A2A mov ecx,[esp+eax*4+0x18] / 0x471A3E lea eax,[ecx*0x2F44+edx+0x48] -> returns record base. So at the CALL (after push ebx) the candidate list is dword record INDEXES at esp+0x18, bound = count (variable, >=1 because 0x471A13 returns 0 when empty). m1 0x415640 calls the picker at 0x415664 and stores the result at [esi+4]. The m1 is called by the selector 0x418870 on every pass (phase select).',
            'note': "Stored at [event+4] by m1 0x415640; m11 0x4156A0: 'Let it go' (choice 1) -> that villager health -15 (0x4156C5) + activity 0xD2 for every believer; 'Search for the bugs all night' (choice 0) -> health -5 if > 6 and like/dislike 0x52. m1 does `mov esi,ecx` before the picker call and the picker saves esi at 0x47187F, so at the site dword [esp+8] = the event object evaluating its condition (use it to tell slots apart when several slots share this m1).",
        },
    ],
    12: [
        {
            'id': 'subject',
            'label': 'Who finds the mask',
            'branch': None,
            'phase': 'select',
            'scope_call': 0x414BB4,
            'kind': 'victim',
            'site': 0x471A25,
            'candidates': {
                'base': {
                    'reg': 'esp',
                    'disp': 0x18,
                },
                'elem': 'index',
                'elem_disp': 0,
                'size': 4,
            },
            'filter': 'record in use (0x466170(0) at 0x4718A8), health [rec+0x1C40] > 0 (0x4718B5), not busy with activity 0xC..0x11 at [rec+0x1CFC] (a14=0, 0x471994..0x4719B6); believers only ([rec+0x1CEC]==0; a11=0,a13=0 -> 0x4719C2..0x4719CD); any age, any sex, pregnant and sick allowed',
            'evidence': 'Picker 0x471870 (thiscall ecx=0x554148, 14 args, ret 0x38): loops i=0..0x95 over records 0x554190+i*0x2F44 (esi=rec+0x1B8C), appends qualifying i to a stack list (0x4719E2 mov [esp+ebx*4+0x14],edi), then 0x471A24 push ebx(count) / 0x471A25 call rand / 0x471A2A mov ecx,[esp+eax*4+0x18] / 0x471A3E lea eax,[ecx*0x2F44+edx+0x48] -> returns record base. So at the CALL (after push ebx) the candidate list is dword record INDEXES at esp+0x18, bound = count (variable, >=1 because 0x471A13 returns 0 when empty). m1 0x414b90 calls the picker at 0x414bb4 and stores the result at [esi+4]. The m1 is called by the selector 0x418870 on every pass (phase select).',
            'note': "Stored at [event+4] by m1 0x414b90; m11 0x415790: 'Put it on' -> SET_FAITH(-10,1) on that villager (0x4157AF, turns them heathen); 'Bury it' -> faith +10 (0x4157BA). m1 does `mov esi,ecx` before the picker call and the picker saves esi at 0x47187F, so at the site dword [esp+8] = the event object evaluating its condition (use it to tell slots apart when several slots share this m1). This m1 is shared by slots 5, 12, 35, 43, 45; the same scope_call evaluates their subjects too.",
        },
    ],
    13: [
        {
            'id': 'child',
            'label': 'Which child finds the toy',
            'branch': None,
            'phase': 'select',
            'scope_call': 0x415848,
            'kind': 'victim',
            'site': 0x471A25,
            'candidates': {
                'base': {
                    'reg': 'esp',
                    'disp': 0x18,
                },
                'elem': 'index',
                'elem_disp': 0,
                'size': 4,
            },
            'filter': 'record in use (0x466170(0) at 0x4718A8), health [rec+0x1C40] > 0 (0x4718B5), not busy with activity 0xC..0x11 at [rec+0x1CFC] (a14=0, 0x471994..0x4719B6); believers only ([rec+0x1CEC]==0; a11=0,a13=0 -> 0x4719C2..0x4719CD); child: age [rec+0x1B8C] < 0x118 (14 years; a2 -> 0x4718E2); pregnant and sick allowed',
            'evidence': 'Picker 0x471870 (thiscall ecx=0x554148, 14 args, ret 0x38): loops i=0..0x95 over records 0x554190+i*0x2F44 (esi=rec+0x1B8C), appends qualifying i to a stack list (0x4719E2 mov [esp+ebx*4+0x14],edi), then 0x471A24 push ebx(count) / 0x471A25 call rand / 0x471A2A mov ecx,[esp+eax*4+0x18] / 0x471A3E lea eax,[ecx*0x2F44+edx+0x48] -> returns record base. So at the CALL (after push ebx) the candidate list is dword record INDEXES at esp+0x18, bound = count (variable, >=1 because 0x471A13 returns 0 when empty). m1 0x415820 calls the picker at 0x415848 and stores the result at [esi+4]. The m1 is called by the selector 0x418870 on every pass (phase select).',
            'note': 'Stored at [event+4] by m1 0x415820; m11 0x4158C0 adds the skill to that child: Research (0x4158F8) if kept, Devotion (0x415903) if returned. m1 does `mov esi,ecx` before the picker call and the picker saves esi at 0x47187F, so at the site dword [esp+8] = the event object evaluating its condition (use it to tell slots apart when several slots share this m1).',
        },
        {
            'id': 'owner',
            'label': 'Which heathen child owns the toy',
            'branch': None,
            'phase': 'select',
            'scope_call': 0x415877,
            'kind': 'victim',
            'site': 0x471A25,
            'candidates': {
                'base': {
                    'reg': 'esp',
                    'disp': 0x18,
                },
                'elem': 'index',
                'elem_disp': 0,
                'size': 4,
            },
            'filter': 'record in use (0x466170(0) at 0x4718A8), health [rec+0x1C40] > 0 (0x4718B5), not busy with activity 0xC..0x11 at [rec+0x1CFC] (a14=0, 0x471994..0x4719B6); heathens only ([rec+0x1CEC]!=0; a11=1 -> 0x471981); child: age [rec+0x1B8C] < 0x118 (14 years; a2 -> 0x4718E2); not sick (byte [rec+0x1C48]==0; a5=0 -> 0x471920); pregnant allowed',
            'evidence': 'Picker 0x471870 (thiscall ecx=0x554148, 14 args, ret 0x38): loops i=0..0x95 over records 0x554190+i*0x2F44 (esi=rec+0x1B8C), appends qualifying i to a stack list (0x4719E2 mov [esp+ebx*4+0x14],edi), then 0x471A24 push ebx(count) / 0x471A25 call rand / 0x471A2A mov ecx,[esp+eax*4+0x18] / 0x471A3E lea eax,[ecx*0x2F44+edx+0x48] -> returns record base. So at the CALL (after push ebx) the candidate list is dword record INDEXES at esp+0x18, bound = count (variable, >=1 because 0x471A13 returns 0 when empty). m1 0x415820 calls the picker at 0x415877 and stores the result at [esi+12]. The m1 is called by the selector 0x418870 on every pass (phase select).',
            'note': "Stored at [event+12] by m1 0x415820; 'Return it to its owner' (choice 1) gives that heathen child faith +15 (0x41590D FAITH_ADD; may convert). m1 does `mov esi,ecx` before the picker call and the picker saves esi at 0x47187F, so at the site dword [esp+8] = the event object evaluating its condition (use it to tell slots apart when several slots share this m1).",
        },
        {
            'id': 'research',
            'label': 'If you keep it: Research gained',
            'branch': 0,
            'phase': 'apply',
            'scope_call': None,
            'kind': 'amount',
            'site': 0x4158D3,
            'bound': 10,
            'base': 20,
            'step': 1,
            'unit': 'skill points (20..29)',
            'evidence': "m11 0x4158C0: 0x4158D1 push 0xA; 0x4158D3 call rand; 0x4158DB add eax,0x14; choice 0 (button 'Keep it', id 2) -> 0x4158F8 SKILL_ADD(3 Research) clamped 0..100. Same site as the 'returned' control: the roll is made before the branch test (0x4158E4), so only the clicked branch's control applies.",
        },
        {
            'id': 'devotion',
            'label': 'If you return it: Devotion gained',
            'branch': 1,
            'phase': 'apply',
            'scope_call': None,
            'kind': 'amount',
            'site': 0x4158D3,
            'bound': 10,
            'base': 20,
            'step': 1,
            'unit': 'skill points (20..29)',
            'evidence': "m11 0x4158C0: same roll 0x4158D3; choice 1 (button 'Return it to its owner', id 3) -> 0x415903 SKILL_ADD(5 Devotion). Same site as the 'kept' control (see there).",
        },
    ],
    14: [
        {
            'id': 'subject',
            'label': 'Who wants to jump',
            'branch': None,
            'phase': 'select',
            'scope_call': 0x415984,
            'kind': 'victim',
            'site': 0x471A25,
            'candidates': {
                'base': {
                    'reg': 'esp',
                    'disp': 0x18,
                },
                'elem': 'index',
                'elem_disp': 0,
                'size': 4,
            },
            'filter': 'record in use (0x466170(0) at 0x4718A8), health [rec+0x1C40] > 0 (0x4718B5), not busy with activity 0xC..0x11 at [rec+0x1CFC] (a14=0, 0x471994..0x4719B6); believers only ([rec+0x1CEC]==0; a11=0,a13=0 -> 0x4719C2..0x4719CD); any age, any sex, pregnant and sick allowed',
            'evidence': 'Picker 0x471870 (thiscall ecx=0x554148, 14 args, ret 0x38): loops i=0..0x95 over records 0x554190+i*0x2F44 (esi=rec+0x1B8C), appends qualifying i to a stack list (0x4719E2 mov [esp+ebx*4+0x14],edi), then 0x471A24 push ebx(count) / 0x471A25 call rand / 0x471A2A mov ecx,[esp+eax*4+0x18] / 0x471A3E lea eax,[ecx*0x2F44+edx+0x48] -> returns record base. So at the CALL (after push ebx) the candidate list is dword record INDEXES at esp+0x18, bound = count (variable, >=1 because 0x471A13 returns 0 when empty). m1 0x415960 calls the picker at 0x415984 and stores the result at [esi+4]. The m1 is called by the selector 0x418870 on every pass (phase select).',
            'note': "Stored at [event+4] by m1 0x415960; m11 0x4159F0 changes that villager's likes/dislikes (0x26/0x30/0x2B if they jump, 0x30/0x28 if not). m1 does `mov esi,ecx` before the picker call and the picker saves esi at 0x47187F, so at the site dword [esp+8] = the event object evaluating its condition (use it to tell slots apart when several slots share this m1).",
        },
    ],
    15: [
        {
            'id': 'weather_length',
            'label': 'How long the weather lasts',
            'branch': None,
            'phase': 'apply',
            'scope_call': 0x414E29,
            'kind': 'amount',
            'site': 0x4771C5,
            'bound': 180,
            'base': 180,
            'step': 1,
            'unit': 'game-clock units of 0x41ED40 after the event (180..359)',
            'evidence': "0x477060(type=4, 0) on 0x718EA0: [esi]=4, jump table 0x47721C[4] = 0x477119; then 0x4771A6 type != 0 -> edi=0xB4, eax=0x168 (0x4771B7/0x4771BC), bound = 0x168-0xB4 = 180 pushed at 0x4771C4, 0x4771C5 call rand, 0x4771D9 ebx+=0xB4, 0x4771DF eax = clock 0x41ED40() + ebx, 0x4771E3 [esi+8] = end time. 0x477060 has 12 callers (natural weather scheduler 0x477298/0x477563/... too), so it is scoped by this event's own call. Scope: apply calls 0x477060(4,0) at 0x414e29.",
            'note': "The event's fire put out part is fixed (no roll).",
        },
    ],
    18: [
        {
            'id': 'tech',
            'label': 'Tech points gained',
            'branch': None,
            'phase': 'apply',
            'scope_call': None,
            'kind': 'amount',
            'site': 0x414EF5,
            'bound': 1000,
            'base': 0x7D0,
            'step': 1,
            'unit': 'tech points (2000..2999)',
            'evidence': '0x414EF0 push 0x3E8; 0x414EF5 call rand; 0x414EFD add eax,0x7D0; 0x414F08 TECH_ADD 0x4237B0 on 0x51D5F8.',
        },
    ],
    23: [
        {
            'id': 'tech_lost',
            'label': 'Tech points lost',
            'branch': None,
            'phase': 'apply',
            'scope_call': None,
            'kind': 'amount',
            'site': 0x415075,
            'bound': 0x9C4,
            'base': 500,
            'step': 1,
            'unit': 'tech points lost (500..2999)',
            'evidence': '0x415070 push 0x9C4; 0x415075 call rand; 0x41507A ecx=-500-v; 0x41508A TECH_ADD; the total is floored at 0 (0x4237FB..0x4237FF), as in stock.',
        },
    ],
    24: [
        {
            'id': 'food',
            'label': 'Food gained',
            'branch': None,
            'phase': 'apply',
            'scope_call': None,
            'kind': 'amount',
            'site': 0x415108,
            'bound': 50,
            'base': 50,
            'step': 1,
            'unit': 'food (50..99, before the farming-tech bonus)',
            'evidence': '0x415106 push 0x32; 0x415108 call rand; 0x415110 add eax,0x32; 0x415119 FOOD_ADD 0x41EB40: positive amounts x1.5 at farming tech (0x51D5CC idx4) level 2, x2 at level 3 (0x41EB4C..0x41EB6D).',
        },
        {
            'id': 'tech_lost',
            'label': 'Tech points lost',
            'branch': None,
            'phase': 'apply',
            'scope_call': None,
            'kind': 'amount',
            'site': 0x415123,
            'bound': 1000,
            'base': 500,
            'step': 1,
            'unit': 'tech points lost (500..1499)',
            'evidence': '0x41511E push 0x3E8; 0x415123 call rand; 0x415128 ecx=-500-v; 0x415138 TECH_ADD (floored at 0, 0x4237FF).',
        },
    ],
    26: [
        {
            'id': 'baby1_sex',
            'label': 'Baby 1: boy or girl',
            'branch': None,
            'phase': 'apply',
            'scope_call': None,
            'kind': 'enum',
            'options': [
                {
                    'label': 'Boy',
                    'force': [
                        [0x4151D7, 0],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise)',
                },
                {
                    'label': 'Girl',
                    'force': [
                        [0x4151D7, 1],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise)',
                },
            ],
            'evidence': "CREATE5 0x471E20 call at 0x415200: push 0xC8 (age 200 = 10 years, fixed), sex rand(2) at 0x4151d7, 5+rand(5) at 0x4151e2 (skill value), rand(6) at 0x4151f0 (skill index), push 1. 0x471E20/0x46FD20 forward a1..a5 unchanged to 0x4681F0 (via 0x46FAD0 / 0x46FB80). a4 sex -> [rec+0x1B90] at 0x468534 (overrides the random sex 0x46F5E0 rolled at 0x468523); 1 = female (0x471AB9 'women volunteer' requires [rec+0x1B90]==1 with age>=0x168 before nursing), 0 = male",
            'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise)',
        },
        {
            'id': 'baby1_skill',
            'label': 'Baby 1: starting skill',
            'branch': None,
            'phase': 'apply',
            'scope_call': None,
            'kind': 'enum',
            'options': [
                {
                    'label': 'Farming',
                    'force': [
                        [0x4151F0, 0],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise)',
                },
                {
                    'label': 'Parenting',
                    'force': [
                        [0x4151F0, 1],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise)',
                },
                {
                    'label': 'Healing',
                    'force': [
                        [0x4151F0, 2],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise)',
                },
                {
                    'label': 'Research',
                    'force': [
                        [0x4151F0, 3],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise)',
                },
                {
                    'label': 'Building',
                    'force': [
                        [0x4151F0, 4],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise)',
                },
                {
                    'label': 'Devotion',
                    'force': [
                        [0x4151F0, 5],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise)',
                },
            ],
            'evidence': 'CREATE5 0x471E20 call at 0x415200: push 0xC8 (age 200 = 10 years, fixed), sex rand(2) at 0x4151d7, 5+rand(5) at 0x4151e2 (skill value), rand(6) at 0x4151f0 (skill index), push 1. 0x471E20/0x46FD20 forward a1..a5 unchanged to 0x4681F0 (via 0x46FAD0 / 0x46FB80). skill index -> rec+0x1C5C float[6] (0x4681F0: 0x4684C5 ecx=a2, 0x4684D4 fst [edi+ecx*4]); order 0 Farming,1 Parenting,2 Healing,3 Research,4 Building,5 Devotion (population_export.c SKILL_NAMES_VV5)',
            'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise)',
        },
        {
            'id': 'baby1_level',
            'label': 'Baby 1: starting skill level',
            'branch': None,
            'phase': 'apply',
            'scope_call': None,
            'kind': 'amount',
            'site': 0x4151E2,
            'bound': 5,
            'base': 5,
            'step': 1,
            'unit': 'skill points (5..9)',
            'evidence': 'CREATE5 0x471E20 call at 0x415200: push 0xC8 (age 200 = 10 years, fixed), sex rand(2) at 0x4151d7, 5+rand(5) at 0x4151e2 (skill value), rand(6) at 0x4151f0 (skill index), push 1. 0x471E20/0x46FD20 forward a1..a5 unchanged to 0x4681F0 (via 0x46FAD0 / 0x46FB80). value stored at 0x4684D4 (clamped 0..100 at 0x4684D7..0x4684FE, never reached for 5..9).',
            'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise)',
        },
        {
            'id': 'baby2_sex',
            'label': 'Baby 2: boy or girl',
            'branch': None,
            'phase': 'apply',
            'scope_call': None,
            'kind': 'enum',
            'options': [
                {
                    'label': 'Boy',
                    'force': [
                        [0x41521A, 0],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
                {
                    'label': 'Girl',
                    'force': [
                        [0x41521A, 1],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
            ],
            'evidence': "CREATE5 0x471E20 call at 0x415243: push 0xC8 (age 200 = 10 years, fixed), sex rand(2) at 0x41521a, 5+rand(5) at 0x415225 (skill value), rand(6) at 0x415233 (skill index), push 1. 0x471E20/0x46FD20 forward a1..a5 unchanged to 0x4681F0 (via 0x46FAD0 / 0x46FB80). a4 sex -> [rec+0x1B90] at 0x468534 (overrides the random sex 0x46F5E0 rolled at 0x468523); 1 = female (0x471AB9 'women volunteer' requires [rec+0x1B90]==1 with age>=0x168 before nursing), 0 = male",
            'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
        },
        {
            'id': 'baby2_skill',
            'label': 'Baby 2: starting skill',
            'branch': None,
            'phase': 'apply',
            'scope_call': None,
            'kind': 'enum',
            'options': [
                {
                    'label': 'Farming',
                    'force': [
                        [0x415233, 0],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
                {
                    'label': 'Parenting',
                    'force': [
                        [0x415233, 1],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
                {
                    'label': 'Healing',
                    'force': [
                        [0x415233, 2],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
                {
                    'label': 'Research',
                    'force': [
                        [0x415233, 3],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
                {
                    'label': 'Building',
                    'force': [
                        [0x415233, 4],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
                {
                    'label': 'Devotion',
                    'force': [
                        [0x415233, 5],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
            ],
            'evidence': 'CREATE5 0x471E20 call at 0x415243: push 0xC8 (age 200 = 10 years, fixed), sex rand(2) at 0x41521a, 5+rand(5) at 0x415225 (skill value), rand(6) at 0x415233 (skill index), push 1. 0x471E20/0x46FD20 forward a1..a5 unchanged to 0x4681F0 (via 0x46FAD0 / 0x46FB80). skill index -> rec+0x1C5C float[6] (0x4681F0: 0x4684C5 ecx=a2, 0x4684D4 fst [edi+ecx*4]); order 0 Farming,1 Parenting,2 Healing,3 Research,4 Building,5 Devotion (population_export.c SKILL_NAMES_VV5)',
            'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
        },
        {
            'id': 'baby2_level',
            'label': 'Baby 2: starting skill level',
            'branch': None,
            'phase': 'apply',
            'scope_call': None,
            'kind': 'amount',
            'site': 0x415225,
            'bound': 5,
            'base': 5,
            'step': 1,
            'unit': 'skill points (5..9)',
            'evidence': 'CREATE5 0x471E20 call at 0x415243: push 0xC8 (age 200 = 10 years, fixed), sex rand(2) at 0x41521a, 5+rand(5) at 0x415225 (skill value), rand(6) at 0x415233 (skill index), push 1. 0x471E20/0x46FD20 forward a1..a5 unchanged to 0x4681F0 (via 0x46FAD0 / 0x46FB80). value stored at 0x4684D4 (clamped 0..100 at 0x4684D7..0x4684FE, never reached for 5..9).',
            'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
        },
        {
            'id': 'baby3_sex',
            'label': 'Baby 3: boy or girl',
            'branch': None,
            'phase': 'apply',
            'scope_call': None,
            'kind': 'enum',
            'options': [
                {
                    'label': 'Boy',
                    'force': [
                        [0x41525D, 0],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
                {
                    'label': 'Girl',
                    'force': [
                        [0x41525D, 1],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
            ],
            'evidence': "CREATE5 0x471E20 call at 0x415286: push 0xC8 (age 200 = 10 years, fixed), sex rand(2) at 0x41525d, 5+rand(5) at 0x415268 (skill value), rand(6) at 0x415276 (skill index), push 1. 0x471E20/0x46FD20 forward a1..a5 unchanged to 0x4681F0 (via 0x46FAD0 / 0x46FB80). a4 sex -> [rec+0x1B90] at 0x468534 (overrides the random sex 0x46F5E0 rolled at 0x468523); 1 = female (0x471AB9 'women volunteer' requires [rec+0x1B90]==1 with age>=0x168 before nursing), 0 = male",
            'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
        },
        {
            'id': 'baby3_skill',
            'label': 'Baby 3: starting skill',
            'branch': None,
            'phase': 'apply',
            'scope_call': None,
            'kind': 'enum',
            'options': [
                {
                    'label': 'Farming',
                    'force': [
                        [0x415276, 0],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
                {
                    'label': 'Parenting',
                    'force': [
                        [0x415276, 1],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
                {
                    'label': 'Healing',
                    'force': [
                        [0x415276, 2],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
                {
                    'label': 'Research',
                    'force': [
                        [0x415276, 3],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
                {
                    'label': 'Building',
                    'force': [
                        [0x415276, 4],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
                {
                    'label': 'Devotion',
                    'force': [
                        [0x415276, 5],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
            ],
            'evidence': 'CREATE5 0x471E20 call at 0x415286: push 0xC8 (age 200 = 10 years, fixed), sex rand(2) at 0x41525d, 5+rand(5) at 0x415268 (skill value), rand(6) at 0x415276 (skill index), push 1. 0x471E20/0x46FD20 forward a1..a5 unchanged to 0x4681F0 (via 0x46FAD0 / 0x46FB80). skill index -> rec+0x1C5C float[6] (0x4681F0: 0x4684C5 ecx=a2, 0x4684D4 fst [edi+ecx*4]); order 0 Farming,1 Parenting,2 Healing,3 Research,4 Building,5 Devotion (population_export.c SKILL_NAMES_VV5)',
            'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
        },
        {
            'id': 'baby3_level',
            'label': 'Baby 3: starting skill level',
            'branch': None,
            'phase': 'apply',
            'scope_call': None,
            'kind': 'amount',
            'site': 0x415268,
            'bound': 5,
            'base': 5,
            'step': 1,
            'unit': 'skill points (5..9)',
            'evidence': 'CREATE5 0x471E20 call at 0x415286: push 0xC8 (age 200 = 10 years, fixed), sex rand(2) at 0x41525d, 5+rand(5) at 0x415268 (skill value), rand(6) at 0x415276 (skill index), push 1. 0x471E20/0x46FD20 forward a1..a5 unchanged to 0x4681F0 (via 0x46FAD0 / 0x46FB80). value stored at 0x4684D4 (clamped 0..100 at 0x4684D7..0x4684FE, never reached for 5..9).',
            'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
        },
    ],
    27: [
        {
            'id': 'baby1_sex',
            'label': 'Baby 1: boy or girl',
            'branch': None,
            'phase': 'apply',
            'scope_call': None,
            'kind': 'enum',
            'options': [
                {
                    'label': 'Boy',
                    'force': [
                        [0x4152BF, 0],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise)',
                },
                {
                    'label': 'Girl',
                    'force': [
                        [0x4152BF, 1],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise)',
                },
            ],
            'evidence': "CREATE_HEATHEN 0x46FD20 (extra args 0,0,0,-55) call at 0x4152e8: push 0xC8 (age 200 = 10 years, fixed), sex rand(2) at 0x4152bf, 5+rand(5) at 0x4152ca (skill value), rand(6) at 0x4152d8 (skill index), push 1. 0x471E20/0x46FD20 forward a1..a5 unchanged to 0x4681F0 (via 0x46FAD0 / 0x46FB80). a4 sex -> [rec+0x1B90] at 0x468534 (overrides the random sex 0x46F5E0 rolled at 0x468523); 1 = female (0x471AB9 'women volunteer' requires [rec+0x1B90]==1 with age>=0x168 before nursing), 0 = male",
            'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise)',
        },
        {
            'id': 'baby1_skill',
            'label': 'Baby 1: starting skill',
            'branch': None,
            'phase': 'apply',
            'scope_call': None,
            'kind': 'enum',
            'options': [
                {
                    'label': 'Farming',
                    'force': [
                        [0x4152D8, 0],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise)',
                },
                {
                    'label': 'Parenting',
                    'force': [
                        [0x4152D8, 1],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise)',
                },
                {
                    'label': 'Healing',
                    'force': [
                        [0x4152D8, 2],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise)',
                },
                {
                    'label': 'Research',
                    'force': [
                        [0x4152D8, 3],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise)',
                },
                {
                    'label': 'Building',
                    'force': [
                        [0x4152D8, 4],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise)',
                },
                {
                    'label': 'Devotion',
                    'force': [
                        [0x4152D8, 5],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise)',
                },
            ],
            'evidence': 'CREATE_HEATHEN 0x46FD20 (extra args 0,0,0,-55) call at 0x4152e8: push 0xC8 (age 200 = 10 years, fixed), sex rand(2) at 0x4152bf, 5+rand(5) at 0x4152ca (skill value), rand(6) at 0x4152d8 (skill index), push 1. 0x471E20/0x46FD20 forward a1..a5 unchanged to 0x4681F0 (via 0x46FAD0 / 0x46FB80). skill index -> rec+0x1C5C float[6] (0x4681F0: 0x4684C5 ecx=a2, 0x4684D4 fst [edi+ecx*4]); order 0 Farming,1 Parenting,2 Healing,3 Research,4 Building,5 Devotion (population_export.c SKILL_NAMES_VV5)',
            'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise)',
        },
        {
            'id': 'baby1_level',
            'label': 'Baby 1: starting skill level',
            'branch': None,
            'phase': 'apply',
            'scope_call': None,
            'kind': 'amount',
            'site': 0x4152CA,
            'bound': 5,
            'base': 5,
            'step': 1,
            'unit': 'skill points (5..9)',
            'evidence': 'CREATE_HEATHEN 0x46FD20 (extra args 0,0,0,-55) call at 0x4152e8: push 0xC8 (age 200 = 10 years, fixed), sex rand(2) at 0x4152bf, 5+rand(5) at 0x4152ca (skill value), rand(6) at 0x4152d8 (skill index), push 1. 0x471E20/0x46FD20 forward a1..a5 unchanged to 0x4681F0 (via 0x46FAD0 / 0x46FB80). value stored at 0x4684D4 (clamped 0..100 at 0x4684D7..0x4684FE, never reached for 5..9).',
            'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise)',
        },
        {
            'id': 'baby2_sex',
            'label': 'Baby 2: boy or girl',
            'branch': None,
            'phase': 'apply',
            'scope_call': None,
            'kind': 'enum',
            'options': [
                {
                    'label': 'Boy',
                    'force': [
                        [0x41530A, 0],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
                {
                    'label': 'Girl',
                    'force': [
                        [0x41530A, 1],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
            ],
            'evidence': "CREATE_HEATHEN 0x46FD20 (extra args 0,0,0,-55) call at 0x415333: push 0xC8 (age 200 = 10 years, fixed), sex rand(2) at 0x41530a, 5+rand(5) at 0x415315 (skill value), rand(6) at 0x415323 (skill index), push 1. 0x471E20/0x46FD20 forward a1..a5 unchanged to 0x4681F0 (via 0x46FAD0 / 0x46FB80). a4 sex -> [rec+0x1B90] at 0x468534 (overrides the random sex 0x46F5E0 rolled at 0x468523); 1 = female (0x471AB9 'women volunteer' requires [rec+0x1B90]==1 with age>=0x168 before nursing), 0 = male",
            'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
        },
        {
            'id': 'baby2_skill',
            'label': 'Baby 2: starting skill',
            'branch': None,
            'phase': 'apply',
            'scope_call': None,
            'kind': 'enum',
            'options': [
                {
                    'label': 'Farming',
                    'force': [
                        [0x415323, 0],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
                {
                    'label': 'Parenting',
                    'force': [
                        [0x415323, 1],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
                {
                    'label': 'Healing',
                    'force': [
                        [0x415323, 2],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
                {
                    'label': 'Research',
                    'force': [
                        [0x415323, 3],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
                {
                    'label': 'Building',
                    'force': [
                        [0x415323, 4],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
                {
                    'label': 'Devotion',
                    'force': [
                        [0x415323, 5],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
            ],
            'evidence': 'CREATE_HEATHEN 0x46FD20 (extra args 0,0,0,-55) call at 0x415333: push 0xC8 (age 200 = 10 years, fixed), sex rand(2) at 0x41530a, 5+rand(5) at 0x415315 (skill value), rand(6) at 0x415323 (skill index), push 1. 0x471E20/0x46FD20 forward a1..a5 unchanged to 0x4681F0 (via 0x46FAD0 / 0x46FB80). skill index -> rec+0x1C5C float[6] (0x4681F0: 0x4684C5 ecx=a2, 0x4684D4 fst [edi+ecx*4]); order 0 Farming,1 Parenting,2 Healing,3 Research,4 Building,5 Devotion (population_export.c SKILL_NAMES_VV5)',
            'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
        },
        {
            'id': 'baby2_level',
            'label': 'Baby 2: starting skill level',
            'branch': None,
            'phase': 'apply',
            'scope_call': None,
            'kind': 'amount',
            'site': 0x415315,
            'bound': 5,
            'base': 5,
            'step': 1,
            'unit': 'skill points (5..9)',
            'evidence': 'CREATE_HEATHEN 0x46FD20 (extra args 0,0,0,-55) call at 0x415333: push 0xC8 (age 200 = 10 years, fixed), sex rand(2) at 0x41530a, 5+rand(5) at 0x415315 (skill value), rand(6) at 0x415323 (skill index), push 1. 0x471E20/0x46FD20 forward a1..a5 unchanged to 0x4681F0 (via 0x46FAD0 / 0x46FB80). value stored at 0x4684D4 (clamped 0..100 at 0x4684D7..0x4684FE, never reached for 5..9).',
            'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
        },
        {
            'id': 'baby3_sex',
            'label': 'Baby 3: boy or girl',
            'branch': None,
            'phase': 'apply',
            'scope_call': None,
            'kind': 'enum',
            'options': [
                {
                    'label': 'Boy',
                    'force': [
                        [0x415355, 0],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
                {
                    'label': 'Girl',
                    'force': [
                        [0x415355, 1],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
            ],
            'evidence': "CREATE_HEATHEN 0x46FD20 (extra args 0,0,0,-55) call at 0x41537e: push 0xC8 (age 200 = 10 years, fixed), sex rand(2) at 0x415355, 5+rand(5) at 0x415360 (skill value), rand(6) at 0x41536e (skill index), push 1. 0x471E20/0x46FD20 forward a1..a5 unchanged to 0x4681F0 (via 0x46FAD0 / 0x46FB80). a4 sex -> [rec+0x1B90] at 0x468534 (overrides the random sex 0x46F5E0 rolled at 0x468523); 1 = female (0x471AB9 'women volunteer' requires [rec+0x1B90]==1 with age>=0x168 before nursing), 0 = male",
            'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
        },
        {
            'id': 'baby3_skill',
            'label': 'Baby 3: starting skill',
            'branch': None,
            'phase': 'apply',
            'scope_call': None,
            'kind': 'enum',
            'options': [
                {
                    'label': 'Farming',
                    'force': [
                        [0x41536E, 0],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
                {
                    'label': 'Parenting',
                    'force': [
                        [0x41536E, 1],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
                {
                    'label': 'Healing',
                    'force': [
                        [0x41536E, 2],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
                {
                    'label': 'Research',
                    'force': [
                        [0x41536E, 3],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
                {
                    'label': 'Building',
                    'force': [
                        [0x41536E, 4],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
                {
                    'label': 'Devotion',
                    'force': [
                        [0x41536E, 5],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
            ],
            'evidence': 'CREATE_HEATHEN 0x46FD20 (extra args 0,0,0,-55) call at 0x41537e: push 0xC8 (age 200 = 10 years, fixed), sex rand(2) at 0x415355, 5+rand(5) at 0x415360 (skill value), rand(6) at 0x41536e (skill index), push 1. 0x471E20/0x46FD20 forward a1..a5 unchanged to 0x4681F0 (via 0x46FAD0 / 0x46FB80). skill index -> rec+0x1C5C float[6] (0x4681F0: 0x4684C5 ecx=a2, 0x4684D4 fst [edi+ecx*4]); order 0 Farming,1 Parenting,2 Healing,3 Research,4 Building,5 Devotion (population_export.c SKILL_NAMES_VV5)',
            'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
        },
        {
            'id': 'baby3_level',
            'label': 'Baby 3: starting skill level',
            'branch': None,
            'phase': 'apply',
            'scope_call': None,
            'kind': 'amount',
            'site': 0x415360,
            'bound': 5,
            'base': 5,
            'step': 1,
            'unit': 'skill points (5..9)',
            'evidence': 'CREATE_HEATHEN 0x46FD20 (extra args 0,0,0,-55) call at 0x41537e: push 0xC8 (age 200 = 10 years, fixed), sex rand(2) at 0x415355, 5+rand(5) at 0x415360 (skill value), rand(6) at 0x41536e (skill index), push 1. 0x471E20/0x46FD20 forward a1..a5 unchanged to 0x4681F0 (via 0x46FAD0 / 0x46FB80). value stored at 0x4684D4 (clamped 0..100 at 0x4684D7..0x4684FE, never reached for 5..9).',
            'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
        },
    ],
    30: [
        {
            'id': 'baby1_sex',
            'label': 'Baby 1: boy or girl',
            'branch': None,
            'phase': 'apply',
            'scope_call': None,
            'kind': 'enum',
            'options': [
                {
                    'label': 'Boy',
                    'force': [
                        [0x415417, 0],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise)',
                },
                {
                    'label': 'Girl',
                    'force': [
                        [0x415417, 1],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise)',
                },
            ],
            'evidence': "CREATE5 0x471E20 call at 0x415440: push 0xC8 (age 200 = 10 years, fixed), sex rand(2) at 0x415417, 5+rand(5) at 0x415422 (skill value), rand(6) at 0x415430 (skill index), push 1. 0x471E20/0x46FD20 forward a1..a5 unchanged to 0x4681F0 (via 0x46FAD0 / 0x46FB80). a4 sex -> [rec+0x1B90] at 0x468534 (overrides the random sex 0x46F5E0 rolled at 0x468523); 1 = female (0x471AB9 'women volunteer' requires [rec+0x1B90]==1 with age>=0x168 before nursing), 0 = male",
            'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise)',
        },
        {
            'id': 'baby1_skill',
            'label': 'Baby 1: starting skill',
            'branch': None,
            'phase': 'apply',
            'scope_call': None,
            'kind': 'enum',
            'options': [
                {
                    'label': 'Farming',
                    'force': [
                        [0x415430, 0],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise)',
                },
                {
                    'label': 'Parenting',
                    'force': [
                        [0x415430, 1],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise)',
                },
                {
                    'label': 'Healing',
                    'force': [
                        [0x415430, 2],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise)',
                },
                {
                    'label': 'Research',
                    'force': [
                        [0x415430, 3],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise)',
                },
                {
                    'label': 'Building',
                    'force': [
                        [0x415430, 4],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise)',
                },
                {
                    'label': 'Devotion',
                    'force': [
                        [0x415430, 5],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise)',
                },
            ],
            'evidence': 'CREATE5 0x471E20 call at 0x415440: push 0xC8 (age 200 = 10 years, fixed), sex rand(2) at 0x415417, 5+rand(5) at 0x415422 (skill value), rand(6) at 0x415430 (skill index), push 1. 0x471E20/0x46FD20 forward a1..a5 unchanged to 0x4681F0 (via 0x46FAD0 / 0x46FB80). skill index -> rec+0x1C5C float[6] (0x4681F0: 0x4684C5 ecx=a2, 0x4684D4 fst [edi+ecx*4]); order 0 Farming,1 Parenting,2 Healing,3 Research,4 Building,5 Devotion (population_export.c SKILL_NAMES_VV5)',
            'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise)',
        },
        {
            'id': 'baby1_level',
            'label': 'Baby 1: starting skill level',
            'branch': None,
            'phase': 'apply',
            'scope_call': None,
            'kind': 'amount',
            'site': 0x415422,
            'bound': 5,
            'base': 5,
            'step': 1,
            'unit': 'skill points (5..9)',
            'evidence': 'CREATE5 0x471E20 call at 0x415440: push 0xC8 (age 200 = 10 years, fixed), sex rand(2) at 0x415417, 5+rand(5) at 0x415422 (skill value), rand(6) at 0x415430 (skill index), push 1. 0x471E20/0x46FD20 forward a1..a5 unchanged to 0x4681F0 (via 0x46FAD0 / 0x46FB80). value stored at 0x4684D4 (clamped 0..100 at 0x4684D7..0x4684FE, never reached for 5..9).',
            'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise)',
        },
        {
            'id': 'baby2_sex',
            'label': 'Baby 2: boy or girl',
            'branch': None,
            'phase': 'apply',
            'scope_call': None,
            'kind': 'enum',
            'options': [
                {
                    'label': 'Boy',
                    'force': [
                        [0x41545A, 0],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
                {
                    'label': 'Girl',
                    'force': [
                        [0x41545A, 1],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
            ],
            'evidence': "CREATE5 0x471E20 call at 0x415483: push 0xC8 (age 200 = 10 years, fixed), sex rand(2) at 0x41545a, 5+rand(5) at 0x415465 (skill value), rand(6) at 0x415473 (skill index), push 1. 0x471E20/0x46FD20 forward a1..a5 unchanged to 0x4681F0 (via 0x46FAD0 / 0x46FB80). a4 sex -> [rec+0x1B90] at 0x468534 (overrides the random sex 0x46F5E0 rolled at 0x468523); 1 = female (0x471AB9 'women volunteer' requires [rec+0x1B90]==1 with age>=0x168 before nursing), 0 = male",
            'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
        },
        {
            'id': 'baby2_skill',
            'label': 'Baby 2: starting skill',
            'branch': None,
            'phase': 'apply',
            'scope_call': None,
            'kind': 'enum',
            'options': [
                {
                    'label': 'Farming',
                    'force': [
                        [0x415473, 0],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
                {
                    'label': 'Parenting',
                    'force': [
                        [0x415473, 1],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
                {
                    'label': 'Healing',
                    'force': [
                        [0x415473, 2],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
                {
                    'label': 'Research',
                    'force': [
                        [0x415473, 3],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
                {
                    'label': 'Building',
                    'force': [
                        [0x415473, 4],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
                {
                    'label': 'Devotion',
                    'force': [
                        [0x415473, 5],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
            ],
            'evidence': 'CREATE5 0x471E20 call at 0x415483: push 0xC8 (age 200 = 10 years, fixed), sex rand(2) at 0x41545a, 5+rand(5) at 0x415465 (skill value), rand(6) at 0x415473 (skill index), push 1. 0x471E20/0x46FD20 forward a1..a5 unchanged to 0x4681F0 (via 0x46FAD0 / 0x46FB80). skill index -> rec+0x1C5C float[6] (0x4681F0: 0x4684C5 ecx=a2, 0x4684D4 fst [edi+ecx*4]); order 0 Farming,1 Parenting,2 Healing,3 Research,4 Building,5 Devotion (population_export.c SKILL_NAMES_VV5)',
            'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
        },
        {
            'id': 'baby2_level',
            'label': 'Baby 2: starting skill level',
            'branch': None,
            'phase': 'apply',
            'scope_call': None,
            'kind': 'amount',
            'site': 0x415465,
            'bound': 5,
            'base': 5,
            'step': 1,
            'unit': 'skill points (5..9)',
            'evidence': 'CREATE5 0x471E20 call at 0x415483: push 0xC8 (age 200 = 10 years, fixed), sex rand(2) at 0x41545a, 5+rand(5) at 0x415465 (skill value), rand(6) at 0x415473 (skill index), push 1. 0x471E20/0x46FD20 forward a1..a5 unchanged to 0x4681F0 (via 0x46FAD0 / 0x46FB80). value stored at 0x4684D4 (clamped 0..100 at 0x4684D7..0x4684FE, never reached for 5..9).',
            'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
        },
        {
            'id': 'baby3_sex',
            'label': 'Baby 3: boy or girl',
            'branch': None,
            'phase': 'apply',
            'scope_call': None,
            'kind': 'enum',
            'options': [
                {
                    'label': 'Boy',
                    'force': [
                        [0x41549D, 0],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
                {
                    'label': 'Girl',
                    'force': [
                        [0x41549D, 1],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
            ],
            'evidence': "CREATE5 0x471E20 call at 0x4154c6: push 0xC8 (age 200 = 10 years, fixed), sex rand(2) at 0x41549d, 5+rand(5) at 0x4154a8 (skill value), rand(6) at 0x4154b6 (skill index), push 1. 0x471E20/0x46FD20 forward a1..a5 unchanged to 0x4681F0 (via 0x46FAD0 / 0x46FB80). a4 sex -> [rec+0x1B90] at 0x468534 (overrides the random sex 0x46F5E0 rolled at 0x468523); 1 = female (0x471AB9 'women volunteer' requires [rec+0x1B90]==1 with age>=0x168 before nursing), 0 = male",
            'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
        },
        {
            'id': 'baby3_skill',
            'label': 'Baby 3: starting skill',
            'branch': None,
            'phase': 'apply',
            'scope_call': None,
            'kind': 'enum',
            'options': [
                {
                    'label': 'Farming',
                    'force': [
                        [0x4154B6, 0],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
                {
                    'label': 'Parenting',
                    'force': [
                        [0x4154B6, 1],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
                {
                    'label': 'Healing',
                    'force': [
                        [0x4154B6, 2],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
                {
                    'label': 'Research',
                    'force': [
                        [0x4154B6, 3],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
                {
                    'label': 'Building',
                    'force': [
                        [0x4154B6, 4],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
                {
                    'label': 'Devotion',
                    'force': [
                        [0x4154B6, 5],
                    ],
                    'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
                },
            ],
            'evidence': 'CREATE5 0x471E20 call at 0x4154c6: push 0xC8 (age 200 = 10 years, fixed), sex rand(2) at 0x41549d, 5+rand(5) at 0x4154a8 (skill value), rand(6) at 0x4154b6 (skill index), push 1. 0x471E20/0x46FD20 forward a1..a5 unchanged to 0x4681F0 (via 0x46FAD0 / 0x46FB80). skill index -> rec+0x1C5C float[6] (0x4681F0: 0x4684C5 ecx=a2, 0x4684D4 fst [edi+ecx*4]); order 0 Farming,1 Parenting,2 Healing,3 Research,4 Building,5 Devotion (population_export.c SKILL_NAMES_VV5)',
            'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
        },
        {
            'id': 'baby3_level',
            'label': 'Baby 3: starting skill level',
            'branch': None,
            'phase': 'apply',
            'scope_call': None,
            'kind': 'amount',
            'site': 0x4154A8,
            'bound': 5,
            'base': 5,
            'step': 1,
            'unit': 'skill points (5..9)',
            'evidence': 'CREATE5 0x471E20 call at 0x4154c6: push 0xC8 (age 200 = 10 years, fixed), sex rand(2) at 0x41549d, 5+rand(5) at 0x4154a8 (skill value), rand(6) at 0x4154b6 (skill index), push 1. 0x471E20/0x46FD20 forward a1..a5 unchanged to 0x4681F0 (via 0x46FAD0 / 0x46FB80). value stored at 0x4684D4 (clamped 0..100 at 0x4684D7..0x4684FE, never reached for 5..9).',
            'condition': 'baby 1 needs a free record (0x46FAD0/0x46FB80 return -1 otherwise); babies 2 and 3 are made only if 0x472BD0 (village has room) is true after the previous one',
        },
    ],
    31: [
        {
            'id': 'skill',
            'label': "The master's skill",
            'branch': None,
            'phase': 'apply',
            'scope_call': None,
            'kind': 'enum',
            'options': [
                {
                    'label': 'Farming',
                    'force': [
                        [0x415520, 0x63],
                        [0x415573, 0],
                    ],
                    'condition': None,
                },
                {
                    'label': 'Parenting',
                    'force': [
                        [0x415520, 0x63],
                        [0x415573, 1],
                    ],
                    'condition': None,
                },
                {
                    'label': 'Healing',
                    'force': [
                        [0x415520, 0x63],
                        [0x415573, 2],
                    ],
                    'condition': None,
                },
                {
                    'label': 'Research',
                    'force': [
                        [0x415520, 0x63],
                        [0x415573, 3],
                    ],
                    'condition': None,
                },
                {
                    'label': 'Building',
                    'force': [
                        [0x415520, 0x63],
                        [0x415573, 4],
                    ],
                    'condition': None,
                },
                {
                    'label': 'Devotion',
                    'force': [
                        [0x415520, 0x63],
                        [0x415573, 5],
                    ],
                    'condition': None,
                },
            ],
            'evidence': 'apply 0x415510: 0x415515 HAS_ROOM else nothing; 0x41551E push 0x64 / 0x415520 call rand; 0x415528 cmp eax,0x32; push 0x168 (age 18y), push 2; jge 0x41555A. r<50: sex 0x415534, level 0x41553F (80+v), skill push 3 fixed, CREATE5 0x415554. r>=50: sex 0x41555A, level 0x415565 (80+v), skill rand(6) at 0x415573, CREATE5 0x415583. skill index -> rec+0x1C5C float[6] (0x4681F0: 0x4684C5 ecx=a2, 0x4684D4 fst [edi+ecx*4]); order 0 Farming,1 Parenting,2 Healing,3 Research,4 Building,5 Devotion (population_export.c SKILL_NAMES_VV5). Forcing 0x415520=99 takes the rand(6) branch for every skill (the r<50 branch only ever gives Research, which is also offered here).',
            'condition': 'room for one villager (0x472BD0 at 0x415515)',
        },
        {
            'id': 'level',
            'label': "The master's skill level",
            'branch': None,
            'phase': 'apply',
            'scope_call': None,
            'kind': 'enum',
            'options': [
                {
                    'label': '80',
                    'force': [
                        [0x41553F, 0],
                        [0x415565, 0],
                    ],
                    'condition': None,
                },
                {
                    'label': '81',
                    'force': [
                        [0x41553F, 1],
                        [0x415565, 1],
                    ],
                    'condition': None,
                },
                {
                    'label': '82',
                    'force': [
                        [0x41553F, 2],
                        [0x415565, 2],
                    ],
                    'condition': None,
                },
                {
                    'label': '83',
                    'force': [
                        [0x41553F, 3],
                        [0x415565, 3],
                    ],
                    'condition': None,
                },
                {
                    'label': '84',
                    'force': [
                        [0x41553F, 4],
                        [0x415565, 4],
                    ],
                    'condition': None,
                },
            ],
            'evidence': 'apply 0x415510: 0x415515 HAS_ROOM else nothing; 0x41551E push 0x64 / 0x415520 call rand; 0x415528 cmp eax,0x32; push 0x168 (age 18y), push 2; jge 0x41555A. r<50: sex 0x415534, level 0x41553F (80+v), skill push 3 fixed, CREATE5 0x415554. r>=50: sex 0x41555A, level 0x415565 (80+v), skill rand(6) at 0x415573, CREATE5 0x415583. Both level sites are forced (only the branch taken runs); value 80+v stored at 0x4684D4 (<=100).',
            'condition': 'room for one villager (0x472BD0 at 0x415515)',
        },
        {
            'id': 'sex',
            'label': 'Man or woman',
            'branch': None,
            'phase': 'apply',
            'scope_call': None,
            'kind': 'enum',
            'options': [
                {
                    'label': 'Man',
                    'force': [
                        [0x415534, 0],
                        [0x41555A, 0],
                    ],
                    'condition': None,
                },
                {
                    'label': 'Woman',
                    'force': [
                        [0x415534, 1],
                        [0x41555A, 1],
                    ],
                    'condition': None,
                },
            ],
            'evidence': "apply 0x415510: 0x415515 HAS_ROOM else nothing; 0x41551E push 0x64 / 0x415520 call rand; 0x415528 cmp eax,0x32; push 0x168 (age 18y), push 2; jge 0x41555A. r<50: sex 0x415534, level 0x41553F (80+v), skill push 3 fixed, CREATE5 0x415554. r>=50: sex 0x41555A, level 0x415565 (80+v), skill rand(6) at 0x415573, CREATE5 0x415583. a4 sex -> [rec+0x1B90] at 0x468534 (overrides the random sex 0x46F5E0 rolled at 0x468523); 1 = female (0x471AB9 'women volunteer' requires [rec+0x1B90]==1 with age>=0x168 before nursing), 0 = male. Both sex sites are forced (bound 2 pushed once at 0x415530 for both).",
            'condition': 'room for one villager (0x472BD0 at 0x415515)',
        },
    ],
    34: [
        {
            'id': 'subject',
            'label': 'Who sneaks into the pools',
            'branch': None,
            'phase': 'select',
            'scope_call': 0x415C65,
            'kind': 'victim',
            'site': 0x471A25,
            'candidates': {
                'base': {
                    'reg': 'esp',
                    'disp': 0x18,
                },
                'elem': 'index',
                'elem_disp': 0,
                'size': 4,
            },
            'filter': 'record in use (0x466170(0) at 0x4718A8), health [rec+0x1C40] > 0 (0x4718B5), not busy with activity 0xC..0x11 at [rec+0x1CFC] (a14=0, 0x471994..0x4719B6); believers only ([rec+0x1CEC]==0; a11=0,a13=0 -> 0x4719C2..0x4719CD); any age, any sex, pregnant and sick allowed',
            'evidence': 'Picker 0x471870 (thiscall ecx=0x554148, 14 args, ret 0x38): loops i=0..0x95 over records 0x554190+i*0x2F44 (esi=rec+0x1B8C), appends qualifying i to a stack list (0x4719E2 mov [esp+ebx*4+0x14],edi), then 0x471A24 push ebx(count) / 0x471A25 call rand / 0x471A2A mov ecx,[esp+eax*4+0x18] / 0x471A3E lea eax,[ecx*0x2F44+edx+0x48] -> returns record base. So at the CALL (after push ebx) the candidate list is dword record INDEXES at esp+0x18, bound = count (variable, >=1 because 0x471A13 returns 0 when empty). m1 0x415c40 calls the picker at 0x415c65 and stores the result at [esi+4]. The m1 is called by the selector 0x418870 on every pass (phase select).',
            'note': "Stored at [event+4] by m1 0x415c40; m11 0x415CD0: 'Bathe quickly' -> health +10 (0x415CF5); 'Enjoy the pools' -> SET_FAITH(-10,1) and SET_FACTION(1) (turns heathen). m1 does `mov esi,ecx` before the picker call and the picker saves esi at 0x47187F, so at the site dword [esp+8] = the event object evaluating its condition (use it to tell slots apart when several slots share this m1). This m1 is shared by slots 34, 47; the same scope_call evaluates their subjects too.",
        },
    ],
    35: [
        {
            'id': 'subject',
            'label': 'Who demands a sign',
            'branch': None,
            'phase': 'select',
            'scope_call': 0x414BB4,
            'kind': 'victim',
            'site': 0x471A25,
            'candidates': {
                'base': {
                    'reg': 'esp',
                    'disp': 0x18,
                },
                'elem': 'index',
                'elem_disp': 0,
                'size': 4,
            },
            'filter': 'record in use (0x466170(0) at 0x4718A8), health [rec+0x1C40] > 0 (0x4718B5), not busy with activity 0xC..0x11 at [rec+0x1CFC] (a14=0, 0x471994..0x4719B6); believers only ([rec+0x1CEC]==0; a11=0,a13=0 -> 0x4719C2..0x4719CD); any age, any sex, pregnant and sick allowed',
            'evidence': 'Picker 0x471870 (thiscall ecx=0x554148, 14 args, ret 0x38): loops i=0..0x95 over records 0x554190+i*0x2F44 (esi=rec+0x1B8C), appends qualifying i to a stack list (0x4719E2 mov [esp+ebx*4+0x14],edi), then 0x471A24 push ebx(count) / 0x471A25 call rand / 0x471A2A mov ecx,[esp+eax*4+0x18] / 0x471A3E lea eax,[ecx*0x2F44+edx+0x48] -> returns record base. So at the CALL (after push ebx) the candidate list is dword record INDEXES at esp+0x18, bound = count (variable, >=1 because 0x471A13 returns 0 when empty). m1 0x414b90 calls the picker at 0x414bb4 and stores the result at [esi+4]. The m1 is called by the selector 0x418870 on every pass (phase select).',
            'note': "Stored at [event+4] by m1 0x414b90; m11 0x415D80: 'Give a sign' -> faith -5 (0x415D9D); 'Don't give a sign' -> faith +5 and Devotion +15 ([0x497F24]). m1 does `mov esi,ecx` before the picker call and the picker saves esi at 0x47187F, so at the site dword [esp+8] = the event object evaluating its condition (use it to tell slots apart when several slots share this m1). This m1 is shared by slots 5, 12, 35, 43, 45; the same scope_call evaluates their subjects too.",
        },
    ],
    36: [
        {
            'id': 'child',
            'label': 'Which child spies',
            'branch': None,
            'phase': 'select',
            'scope_call': 0x415E48,
            'kind': 'victim',
            'site': 0x471A25,
            'candidates': {
                'base': {
                    'reg': 'esp',
                    'disp': 0x18,
                },
                'elem': 'index',
                'elem_disp': 0,
                'size': 4,
            },
            'filter': 'record in use (0x466170(0) at 0x4718A8), health [rec+0x1C40] > 0 (0x4718B5), not busy with activity 0xC..0x11 at [rec+0x1CFC] (a14=0, 0x471994..0x4719B6); believers only ([rec+0x1CEC]==0; a11=0,a13=0 -> 0x4719C2..0x4719CD); child: age [rec+0x1B8C] < 0x118 (14 years; a2 -> 0x4718E2); pregnant and sick allowed',
            'evidence': 'Picker 0x471870 (thiscall ecx=0x554148, 14 args, ret 0x38): loops i=0..0x95 over records 0x554190+i*0x2F44 (esi=rec+0x1B8C), appends qualifying i to a stack list (0x4719E2 mov [esp+ebx*4+0x14],edi), then 0x471A24 push ebx(count) / 0x471A25 call rand / 0x471A2A mov ecx,[esp+eax*4+0x18] / 0x471A3E lea eax,[ecx*0x2F44+edx+0x48] -> returns record base. So at the CALL (after push ebx) the candidate list is dword record INDEXES at esp+0x18, bound = count (variable, >=1 because 0x471A13 returns 0 when empty). m1 0x415e20 calls the picker at 0x415e48 and stores the result at [esi+4]. The m1 is called by the selector 0x418870 on every pass (phase select).',
            'note': "Stored at [event+4] by m1 0x415e20; m11 0x415EB0: Devotion +15 ([0x497F24], 'Run away') or +25 ([0x497F6C], 'Talk to the heathen'). m1 does `mov esi,ecx` before the picker call and the picker saves esi at 0x47187F, so at the site dword [esp+8] = the event object evaluating its condition (use it to tell slots apart when several slots share this m1). This m1 is shared by slots 36, 38; the same scope_call evaluates their subjects too.",
        },
        {
            'id': 'heathen',
            'label': 'Which heathen catches the child',
            'branch': None,
            'phase': 'select',
            'scope_call': 0x415E80,
            'kind': 'victim',
            'site': 0x471A25,
            'candidates': {
                'base': {
                    'reg': 'esp',
                    'disp': 0x18,
                },
                'elem': 'index',
                'elem_disp': 0,
                'size': 4,
            },
            'filter': 'record in use (0x466170(0) at 0x4718A8), health [rec+0x1C40] > 0 (0x4718B5), not busy with activity 0xC..0x11 at [rec+0x1CFC] (a14=0, 0x471994..0x4719B6); heathens only ([rec+0x1CEC]!=0; a11=1 -> 0x471981); child: age [rec+0x1B8C] < 0x118 (14 years; a2 -> 0x4718E2); not sick (byte [rec+0x1C48]==0; a5=0 -> 0x471920); pregnant allowed',
            'evidence': 'Picker 0x471870 (thiscall ecx=0x554148, 14 args, ret 0x38): loops i=0..0x95 over records 0x554190+i*0x2F44 (esi=rec+0x1B8C), appends qualifying i to a stack list (0x4719E2 mov [esp+ebx*4+0x14],edi), then 0x471A24 push ebx(count) / 0x471A25 call rand / 0x471A2A mov ecx,[esp+eax*4+0x18] / 0x471A3E lea eax,[ecx*0x2F44+edx+0x48] -> returns record base. So at the CALL (after push ebx) the candidate list is dword record INDEXES at esp+0x18, bound = count (variable, >=1 because 0x471A13 returns 0 when empty). m1 0x415e20 calls the picker at 0x415e80 and stores the result at [esi+12]. The m1 is called by the selector 0x418870 on every pass (phase select).',
            'note': "Stored at [event+12] by m1 0x415e20; 'Talk to the heathen' (choice 1) gives that heathen faith +5 (0x415EFB; may convert). m1 does `mov esi,ecx` before the picker call and the picker saves esi at 0x47187F, so at the site dword [esp+8] = the event object evaluating its condition (use it to tell slots apart when several slots share this m1). This m1 is shared by slots 36, 38; the same scope_call evaluates their subjects too.",
        },
    ],
    37: [
        {
            'id': 'subject',
            'label': 'Who tries to stop the heathens',
            'branch': None,
            'phase': 'select',
            'scope_call': 0x415F88,
            'kind': 'victim',
            'site': 0x471A25,
            'candidates': {
                'base': {
                    'reg': 'esp',
                    'disp': 0x18,
                },
                'elem': 'index',
                'elem_disp': 0,
                'size': 4,
            },
            'filter': 'record in use (0x466170(0) at 0x4718A8), health [rec+0x1C40] > 0 (0x4718B5), not busy with activity 0xC..0x11 at [rec+0x1CFC] (a14=0, 0x471994..0x4719B6); believers only ([rec+0x1CEC]==0; a11=0,a13=0 -> 0x4719C2..0x4719CD); adult: age [rec+0x1B8C] >= 0x118 (14 years; a1 -> 0x4718CE); pregnant and sick allowed',
            'evidence': 'Picker 0x471870 (thiscall ecx=0x554148, 14 args, ret 0x38): loops i=0..0x95 over records 0x554190+i*0x2F44 (esi=rec+0x1B8C), appends qualifying i to a stack list (0x4719E2 mov [esp+ebx*4+0x14],edi), then 0x471A24 push ebx(count) / 0x471A25 call rand / 0x471A2A mov ecx,[esp+eax*4+0x18] / 0x471A3E lea eax,[ecx*0x2F44+edx+0x48] -> returns record base. So at the CALL (after push ebx) the candidate list is dword record INDEXES at esp+0x18, bound = count (variable, >=1 because 0x471A13 returns 0 when empty). m1 0x415f60 calls the picker at 0x415f88 and stores the result at [esi+4]. The m1 is called by the selector 0x418870 on every pass (phase select).',
            'note': 'Stored at [event+4] by m1 0x415f60; m11 0x416020: on the explosion result that villager loses health (0x41605B) and gets like/dislike 0x51. m1 does `mov esi,ecx` before the picker call and the picker saves esi at 0x47187F, so at the site dword [esp+8] = the event object evaluating its condition (use it to tell slots apart when several slots share this m1).',
        },
        {
            'id': 'result',
            'label': 'If you teach them',
            'branch': 0,
            'phase': 'select',
            'scope_call': None,
            'kind': 'enum',
            'options': [
                {
                    'label': 'An explosion hurts the villager',
                    'force': [
                        [0x415FDF, 0],
                    ],
                    'condition': None,
                },
                {
                    'label': 'They stop mixing acids (science technology +1 level)',
                    'force': [
                        [0x415FDF, 0x63],
                    ],
                    'condition': 'science technology (0x51D5CC idx 0) level < 2 (also required by m1 at 0x415FD3..0x415FDB; m11 rechecks at 0x41608D)',
                },
            ],
            'evidence': "m1 0x415F60: 0x415FDD push 0x64; 0x415FDF call rand; 0x415FE9 cmp eax,0x32 / setge -> [event+0x10]. m10 0x416000 (choice 0): text 0x3DB + ([+0x10]!=0); m11 0x416020 choice 0 (button 'Teach them to reduce explosions.', id 2): [+0x10]==0 -> health loss + like/dislike 0x51 (0x416038..0x41607E); ==1 -> 0x423610(0,1) science technology (0x51D5CC idx 0) +1 level if < 2. Choice 1 ('There are a lot of them; better not!') is fixed +500 tech (0x4160A5). m1 0x415F60 belongs to slot 37 only; it runs on every selector pass, the last call before the dialog decides.",
        },
        {
            'id': 'health_lost',
            'label': 'If you teach them and it explodes: health lost',
            'branch': 0,
            'phase': 'apply',
            'scope_call': None,
            'kind': 'amount',
            'site': 0x416042,
            'bound': 20,
            'base': 10,
            'step': 1,
            'unit': 'health lost (10..29)',
            'evidence': 'm11 0x416020: 0x416040 push 0x14; 0x416042 call rand; 0x416047 ecx=-10-v; 0x41605B HEALTH_ADD 0x4758F0 (cause -1): health += -10-v; at <= 0 it is set to 0 with the cause (0x4758F0) -- stock can do the same.',
            'condition': 'only on the explosion result ([event+0x10]==0)',
        },
    ],
    38: [
        {
            'id': 'child',
            'label': 'Which child is missing',
            'branch': None,
            'phase': 'select',
            'scope_call': 0x415E48,
            'kind': 'victim',
            'site': 0x471A25,
            'candidates': {
                'base': {
                    'reg': 'esp',
                    'disp': 0x18,
                },
                'elem': 'index',
                'elem_disp': 0,
                'size': 4,
            },
            'filter': 'record in use (0x466170(0) at 0x4718A8), health [rec+0x1C40] > 0 (0x4718B5), not busy with activity 0xC..0x11 at [rec+0x1CFC] (a14=0, 0x471994..0x4719B6); believers only ([rec+0x1CEC]==0; a11=0,a13=0 -> 0x4719C2..0x4719CD); child: age [rec+0x1B8C] < 0x118 (14 years; a2 -> 0x4718E2); pregnant and sick allowed',
            'evidence': 'Picker 0x471870 (thiscall ecx=0x554148, 14 args, ret 0x38): loops i=0..0x95 over records 0x554190+i*0x2F44 (esi=rec+0x1B8C), appends qualifying i to a stack list (0x4719E2 mov [esp+ebx*4+0x14],edi), then 0x471A24 push ebx(count) / 0x471A25 call rand / 0x471A2A mov ecx,[esp+eax*4+0x18] / 0x471A3E lea eax,[ecx*0x2F44+edx+0x48] -> returns record base. So at the CALL (after push ebx) the candidate list is dword record INDEXES at esp+0x18, bound = count (variable, >=1 because 0x471A13 returns 0 when empty). m1 0x415e20 calls the picker at 0x415e48 and stores the result at [esi+4]. The m1 is called by the selector 0x418870 on every pass (phase select).',
            'note': "Stored at [event+4] by m1 0x415e20; m11 0x416120: 'Yell for help' -> health -5 and sick (byte +0x1C48 = 1); 'Try to help the heathen' -> Devotion +10 ([0x497FFC]). m1 does `mov esi,ecx` before the picker call and the picker saves esi at 0x47187F, so at the site dword [esp+8] = the event object evaluating its condition (use it to tell slots apart when several slots share this m1). This m1 is shared by slots 36, 38; the same scope_call evaluates their subjects too.",
        },
        {
            'id': 'heathen',
            'label': 'Which heathen is suspected',
            'branch': None,
            'phase': 'select',
            'scope_call': 0x415E80,
            'kind': 'victim',
            'site': 0x471A25,
            'candidates': {
                'base': {
                    'reg': 'esp',
                    'disp': 0x18,
                },
                'elem': 'index',
                'elem_disp': 0,
                'size': 4,
            },
            'filter': 'record in use (0x466170(0) at 0x4718A8), health [rec+0x1C40] > 0 (0x4718B5), not busy with activity 0xC..0x11 at [rec+0x1CFC] (a14=0, 0x471994..0x4719B6); heathens only ([rec+0x1CEC]!=0; a11=1 -> 0x471981); child: age [rec+0x1B8C] < 0x118 (14 years; a2 -> 0x4718E2); not sick (byte [rec+0x1C48]==0; a5=0 -> 0x471920); pregnant allowed',
            'evidence': 'Picker 0x471870 (thiscall ecx=0x554148, 14 args, ret 0x38): loops i=0..0x95 over records 0x554190+i*0x2F44 (esi=rec+0x1B8C), appends qualifying i to a stack list (0x4719E2 mov [esp+ebx*4+0x14],edi), then 0x471A24 push ebx(count) / 0x471A25 call rand / 0x471A2A mov ecx,[esp+eax*4+0x18] / 0x471A3E lea eax,[ecx*0x2F44+edx+0x48] -> returns record base. So at the CALL (after push ebx) the candidate list is dword record INDEXES at esp+0x18, bound = count (variable, >=1 because 0x471A13 returns 0 when empty). m1 0x415e20 calls the picker at 0x415e80 and stores the result at [esi+12]. The m1 is called by the selector 0x418870 on every pass (phase select).',
            'note': "Stored at [event+12] by m1 0x415e20; 'Yell for help' -> health -5 and sick (0x4161F0, 0x416203); 'Try to help the heathen' -> faith +10 (0x41622D; may convert). m1 does `mov esi,ecx` before the picker call and the picker saves esi at 0x47187F, so at the site dword [esp+8] = the event object evaluating its condition (use it to tell slots apart when several slots share this m1). This m1 is shared by slots 36, 38; the same scope_call evaluates their subjects too.",
        },
    ],
    39: [
        {
            'id': 'envoy',
            'label': 'Which heathen is the envoy',
            'branch': None,
            'phase': 'select',
            'scope_call': 0x4162E0,
            'kind': 'victim',
            'site': 0x471A25,
            'candidates': {
                'base': {
                    'reg': 'esp',
                    'disp': 0x18,
                },
                'elem': 'index',
                'elem_disp': 0,
                'size': 4,
            },
            'filter': 'record in use (0x466170(0) at 0x4718A8), health [rec+0x1C40] > 0 (0x4718B5), not busy with activity 0xC..0x11 at [rec+0x1CFC] (a14=0, 0x471994..0x4719B6); heathens only ([rec+0x1CEC]!=0; a11=1 -> 0x471981); adult: age [rec+0x1B8C] >= 0x118 (14 years; a1 -> 0x4718CE); not sick (byte [rec+0x1C48]==0; a5=0 -> 0x471920); pregnant allowed',
            'evidence': 'Picker 0x471870 (thiscall ecx=0x554148, 14 args, ret 0x38): loops i=0..0x95 over records 0x554190+i*0x2F44 (esi=rec+0x1B8C), appends qualifying i to a stack list (0x4719E2 mov [esp+ebx*4+0x14],edi), then 0x471A24 push ebx(count) / 0x471A25 call rand / 0x471A2A mov ecx,[esp+eax*4+0x18] / 0x471A3E lea eax,[ecx*0x2F44+edx+0x48] -> returns record base. So at the CALL (after push ebx) the candidate list is dword record INDEXES at esp+0x18, bound = count (variable, >=1 because 0x471A13 returns 0 when empty). m1 0x416280 calls the picker at 0x4162e0 and stores the result at [esi+4]. The m1 is called by the selector 0x418870 on every pass (phase select).',
            'note': "Stored at [event+4] by m1 0x416280; 'Offer a tour' (choice 0): byte [envoy+0x1CED] = 0 (0x41632F) and faith +20 (0x4163AB; may convert). m1 does `mov esi,ecx` before the picker call and the picker saves esi at 0x47187F, so at the site dword [esp+8] = the event object evaluating its condition (use it to tell slots apart when several slots share this m1).",
        },
        {
            'id': 'guide',
            'label': 'Which believer gives the tour',
            'branch': None,
            'phase': 'select',
            'scope_call': 0x4162A8,
            'kind': 'victim',
            'site': 0x471A25,
            'candidates': {
                'base': {
                    'reg': 'esp',
                    'disp': 0x18,
                },
                'elem': 'index',
                'elem_disp': 0,
                'size': 4,
            },
            'filter': 'record in use (0x466170(0) at 0x4718A8), health [rec+0x1C40] > 0 (0x4718B5), not busy with activity 0xC..0x11 at [rec+0x1CFC] (a14=0, 0x471994..0x4719B6); believers only ([rec+0x1CEC]==0; a11=0,a13=0 -> 0x4719C2..0x4719CD); adult: age [rec+0x1B8C] >= 0x118 (14 years; a1 -> 0x4718CE); pregnant and sick allowed',
            'evidence': 'Picker 0x471870 (thiscall ecx=0x554148, 14 args, ret 0x38): loops i=0..0x95 over records 0x554190+i*0x2F44 (esi=rec+0x1B8C), appends qualifying i to a stack list (0x4719E2 mov [esp+ebx*4+0x14],edi), then 0x471A24 push ebx(count) / 0x471A25 call rand / 0x471A2A mov ecx,[esp+eax*4+0x18] / 0x471A3E lea eax,[ecx*0x2F44+edx+0x48] -> returns record base. So at the CALL (after push ebx) the candidate list is dword record INDEXES at esp+0x18, bound = count (variable, >=1 because 0x471A13 returns 0 when empty). m1 0x416280 calls the picker at 0x4162a8 and stores the result at [esi+12]. The m1 is called by the selector 0x418870 on every pass (phase select).',
            'note': "Stored at [event+12] by m1 0x416280; 'Offer a tour' (choice 0): Devotion +20 ([0x498044], 0x4163C5). m1 does `mov esi,ecx` before the picker call and the picker saves esi at 0x47187F, so at the site dword [esp+8] = the event object evaluating its condition (use it to tell slots apart when several slots share this m1).",
        },
    ],
    40: [
        {
            'id': 'subject',
            'label': 'Which researcher finds the artifacts',
            'branch': None,
            'phase': 'select',
            'scope_call': 0x41647E,
            'kind': 'victim',
            'site': 0x471A25,
            'candidates': {
                'base': {
                    'reg': 'esp',
                    'disp': 0x18,
                },
                'elem': 'index',
                'elem_disp': 0,
                'size': 4,
            },
            'filter': 'record in use (0x466170(0) at 0x4718A8), health [rec+0x1C40] > 0 (0x4718B5), not busy with activity 0xC..0x11 at [rec+0x1CFC] (a14=0, 0x471994..0x4719B6); believers only ([rec+0x1CEC]==0; a11=0,a13=0 -> 0x4719C2..0x4719CD); any age, any sex, pregnant and sick allowed',
            'evidence': 'Picker 0x471870 (thiscall ecx=0x554148, 14 args, ret 0x38): loops i=0..0x95 over records 0x554190+i*0x2F44 (esi=rec+0x1B8C), appends qualifying i to a stack list (0x4719E2 mov [esp+ebx*4+0x14],edi), then 0x471A24 push ebx(count) / 0x471A25 call rand / 0x471A2A mov ecx,[esp+eax*4+0x18] / 0x471A3E lea eax,[ecx*0x2F44+edx+0x48] -> returns record base. So at the CALL (after push ebx) the candidate list is dword record INDEXES at esp+0x18, bound = count (variable, >=1 because 0x471A13 returns 0 when empty). m1 0x416430 calls the picker at 0x41647e and stores the result at [esi+4]. The m1 is called by the selector 0x418870 on every pass (phase select).',
            'note': 'Stored at [event+4] by m1 0x416430; m11 0x4164E0: Research +40 on a well-received report (0x416513); like/dislike 0x27 otherwise. m1 does `mov esi,ecx` before the picker call and the picker saves esi at 0x47187F, so at the site dword [esp+8] = the event object evaluating its condition (use it to tell slots apart when several slots share this m1).',
        },
        {
            'id': 'result',
            'label': 'If you prepare an independent report',
            'branch': 1,
            'phase': 'select',
            'scope_call': None,
            'kind': 'enum',
            'options': [
                {
                    'label': 'Well received (Research +40, science technology +1 level)',
                    'force': [
                        [0x41644A, 0x63],
                    ],
                    'condition': 'science technology (0x51D5CC idx 0) level == 2 (m1 0x41643F >= 2 and 0x416496 < 3)',
                },
                {
                    'label': 'Not believed (-100 tech)',
                    'force': [
                        [0x41644A, 0],
                    ],
                    'condition': None,
                },
            ],
            'evidence': "m1 0x416430: 0x416448 push 0x64; 0x41644A call rand; 0x416466 cmp eax,0x32 / 0x41646B setge -> 0x416476 [event+0x10]. m10 0x4164B0 (choice 1): text 0x3EE + ([+0x10]!=1). m11 0x4164E0 choice 1 (button 'Prepare an independent report.', id 3): [+0x10]==1 -> Research +[0x49808C]=40 and 0x423610(0,1); else like/dislike 0x27 and TECH_ADD(-100). Choice 0 ('Collaborate') fixed +2000 tech. m1 0x416430 belongs to slot 40 only.",
        },
    ],
    41: [
        {
            'id': 'subject',
            'label': 'Who finds the scrolls',
            'branch': None,
            'phase': 'select',
            'scope_call': 0x416601,
            'kind': 'victim',
            'site': 0x471A25,
            'candidates': {
                'base': {
                    'reg': 'esp',
                    'disp': 0x18,
                },
                'elem': 'index',
                'elem_disp': 0,
                'size': 4,
            },
            'filter': 'record in use (0x466170(0) at 0x4718A8), health [rec+0x1C40] > 0 (0x4718B5), not busy with activity 0xC..0x11 at [rec+0x1CFC] (a14=0, 0x471994..0x4719B6); believers only ([rec+0x1CEC]==0; a11=0,a13=0 -> 0x4719C2..0x4719CD); any age, any sex, pregnant and sick allowed',
            'evidence': 'Picker 0x471870 (thiscall ecx=0x554148, 14 args, ret 0x38): loops i=0..0x95 over records 0x554190+i*0x2F44 (esi=rec+0x1B8C), appends qualifying i to a stack list (0x4719E2 mov [esp+ebx*4+0x14],edi), then 0x471A24 push ebx(count) / 0x471A25 call rand / 0x471A2A mov ecx,[esp+eax*4+0x18] / 0x471A3E lea eax,[ecx*0x2F44+edx+0x48] -> returns record base. So at the CALL (after push ebx) the candidate list is dword record INDEXES at esp+0x18, bound = count (variable, >=1 because 0x471A13 returns 0 when empty). m1 0x4165d0 calls the picker at 0x416601 and stores the result at [esi+4]. The m1 is called by the selector 0x418870 on every pass (phase select).',
            'note': "Stored at [event+4] by m1 0x4165d0; m11 0x416630: 'Employ a clever ruse' -> that villager's Devotion set to 0 (0x41665C); 'Trade' -> Devotion +35 ([0x4980D8]). m1 does `mov esi,ecx` before the picker call and the picker saves esi at 0x47187F, so at the site dword [esp+8] = the event object evaluating its condition (use it to tell slots apart when several slots share this m1).",
        },
    ],
    42: [
        {
            'id': 'child',
            'label': 'Which child the bats are about',
            'branch': None,
            'phase': 'select',
            'scope_call': 0x416717,
            'kind': 'victim',
            'site': 0x471A25,
            'candidates': {
                'base': {
                    'reg': 'esp',
                    'disp': 0x18,
                },
                'elem': 'index',
                'elem_disp': 0,
                'size': 4,
            },
            'filter': 'record in use (0x466170(0) at 0x4718A8), health [rec+0x1C40] > 0 (0x4718B5), not busy with activity 0xC..0x11 at [rec+0x1CFC] (a14=0, 0x471994..0x4719B6); believers only ([rec+0x1CEC]==0; a11=0,a13=0 -> 0x4719C2..0x4719CD); child: age [rec+0x1B8C] < 0x118 (14 years; a2 -> 0x4718E2); pregnant and sick allowed',
            'evidence': 'Picker 0x471870 (thiscall ecx=0x554148, 14 args, ret 0x38): loops i=0..0x95 over records 0x554190+i*0x2F44 (esi=rec+0x1B8C), appends qualifying i to a stack list (0x4719E2 mov [esp+ebx*4+0x14],edi), then 0x471A24 push ebx(count) / 0x471A25 call rand / 0x471A2A mov ecx,[esp+eax*4+0x18] / 0x471A3E lea eax,[ecx*0x2F44+edx+0x48] -> returns record base. So at the CALL (after push ebx) the candidate list is dword record INDEXES at esp+0x18, bound = count (variable, >=1 because 0x471A13 returns 0 when empty). m1 0x4166f0 calls the picker at 0x416717 and stores the result at [esi+4]. The m1 is called by the selector 0x418870 on every pass (phase select).',
            'note': "Stored at [event+4] by m1 0x4166f0; m11 0x416760: 'Scare them' (choice 1) -> that child's Farming +25 ([0x497F6C], 0x4167AE); 'Observe them' changes no villager. m1 does `mov esi,ecx` before the picker call and the picker saves esi at 0x47187F, so at the site dword [esp+8] = the event object evaluating its condition (use it to tell slots apart when several slots share this m1).",
        },
    ],
    43: [
        {
            'id': 'subject',
            'label': 'Who deals with the aphids',
            'branch': None,
            'phase': 'select',
            'scope_call': 0x414BB4,
            'kind': 'victim',
            'site': 0x471A25,
            'candidates': {
                'base': {
                    'reg': 'esp',
                    'disp': 0x18,
                },
                'elem': 'index',
                'elem_disp': 0,
                'size': 4,
            },
            'filter': 'record in use (0x466170(0) at 0x4718A8), health [rec+0x1C40] > 0 (0x4718B5), not busy with activity 0xC..0x11 at [rec+0x1CFC] (a14=0, 0x471994..0x4719B6); believers only ([rec+0x1CEC]==0; a11=0,a13=0 -> 0x4719C2..0x4719CD); any age, any sex, pregnant and sick allowed',
            'evidence': 'Picker 0x471870 (thiscall ecx=0x554148, 14 args, ret 0x38): loops i=0..0x95 over records 0x554190+i*0x2F44 (esi=rec+0x1B8C), appends qualifying i to a stack list (0x4719E2 mov [esp+ebx*4+0x14],edi), then 0x471A24 push ebx(count) / 0x471A25 call rand / 0x471A2A mov ecx,[esp+eax*4+0x18] / 0x471A3E lea eax,[ecx*0x2F44+edx+0x48] -> returns record base. So at the CALL (after push ebx) the candidate list is dword record INDEXES at esp+0x18, bound = count (variable, >=1 because 0x471A13 returns 0 when empty). m1 0x414b90 calls the picker at 0x414bb4 and stores the result at [esi+4]. The m1 is called by the selector 0x418870 on every pass (phase select).',
            'note': "Stored at [event+4] by m1 0x414b90; m11 0x416830: 'Research bugs that eat aphids' -> Farming +40 ([0x49808C], 0x41688B). m1 does `mov esi,ecx` before the picker call and the picker saves esi at 0x47187F, so at the site dword [esp+8] = the event object evaluating its condition (use it to tell slots apart when several slots share this m1). This m1 is shared by slots 5, 12, 35, 43, 45; the same scope_call evaluates their subjects too.",
        },
    ],
    44: [
        {
            'id': 'heathen',
            'label': 'Which heathen asks to join',
            'branch': None,
            'phase': 'select',
            'scope_call': 0x41693D,
            'kind': 'victim',
            'site': 0x471A25,
            'candidates': {
                'base': {
                    'reg': 'esp',
                    'disp': 0x18,
                },
                'elem': 'index',
                'elem_disp': 0,
                'size': 4,
            },
            'filter': 'record in use (0x466170(0) at 0x4718A8), health [rec+0x1C40] > 0 (0x4718B5), not busy with activity 0xC..0x11 at [rec+0x1CFC] (a14=0, 0x471994..0x4719B6); heathens only ([rec+0x1CEC]!=0; a11=1 -> 0x471981); not sick (byte [rec+0x1C48]==0; a5=0 -> 0x471920); any age, pregnant allowed',
            'evidence': 'Picker 0x471870 (thiscall ecx=0x554148, 14 args, ret 0x38): loops i=0..0x95 over records 0x554190+i*0x2F44 (esi=rec+0x1B8C), appends qualifying i to a stack list (0x4719E2 mov [esp+ebx*4+0x14],edi), then 0x471A24 push ebx(count) / 0x471A25 call rand / 0x471A2A mov ecx,[esp+eax*4+0x18] / 0x471A3E lea eax,[ecx*0x2F44+edx+0x48] -> returns record base. So at the CALL (after push ebx) the candidate list is dword record INDEXES at esp+0x18, bound = count (variable, >=1 because 0x471A13 returns 0 when empty). m1 0x416900 calls the picker at 0x41693d and stores the result at [esi+4]. The m1 is called by the selector 0x418870 on every pass (phase select).',
            'note': 'Stored at [event+4] by m1 0x416900; m11 0x416970: genuine defector -> SET_FAITH(20,1) and SET_FACTION(0) (0x416995/0x41699F). m1 does `mov esi,ecx` before the picker call and the picker saves esi at 0x47187F, so at the site dword [esp+8] = the event object evaluating its condition (use it to tell slots apart when several slots share this m1).',
        },
        {
            'id': 'result',
            'label': 'If you accept the heathen',
            'branch': 0,
            'phase': 'select',
            'scope_call': None,
            'kind': 'enum',
            'options': [
                {
                    'label': 'A genuine defector joins the believers',
                    'force': [
                        [0x416906, 0],
                    ],
                    'condition': None,
                },
                {
                    'label': 'It was a spy (-2000 tech)',
                    'force': [
                        [0x416906, 0x63],
                    ],
                    'condition': None,
                },
            ],
            'evidence': "m1 0x416900: 0x416902 push 0x64; 0x416906 call rand; 0x416925 cmp eax,0x32 / 0x41692A setge -> 0x416935 [event+0x10]. m10 0x416950 (choice 0): text 0x407 + ([+0x10]!=0). m11 0x416970 choice 0 (button 'Accept the heathen', id 2): [+0x10]==0 -> SET_FAITH(20,1) + SET_FACTION(0); ==1 -> TECH_ADD(-2000) (0x4169A8). Choice 1 ('Better not') does nothing. The roll does not gate eligibility (0x416945 setne on the picker only). m1 0x416900 belongs to slot 44 only.",
        },
    ],
    45: [
        {
            'id': 'subject',
            'label': 'Who finds the straw thing',
            'branch': None,
            'phase': 'select',
            'scope_call': 0x414BB4,
            'kind': 'victim',
            'site': 0x471A25,
            'candidates': {
                'base': {
                    'reg': 'esp',
                    'disp': 0x18,
                },
                'elem': 'index',
                'elem_disp': 0,
                'size': 4,
            },
            'filter': 'record in use (0x466170(0) at 0x4718A8), health [rec+0x1C40] > 0 (0x4718B5), not busy with activity 0xC..0x11 at [rec+0x1CFC] (a14=0, 0x471994..0x4719B6); believers only ([rec+0x1CEC]==0; a11=0,a13=0 -> 0x4719C2..0x4719CD); any age, any sex, pregnant and sick allowed',
            'evidence': 'Picker 0x471870 (thiscall ecx=0x554148, 14 args, ret 0x38): loops i=0..0x95 over records 0x554190+i*0x2F44 (esi=rec+0x1B8C), appends qualifying i to a stack list (0x4719E2 mov [esp+ebx*4+0x14],edi), then 0x471A24 push ebx(count) / 0x471A25 call rand / 0x471A2A mov ecx,[esp+eax*4+0x18] / 0x471A3E lea eax,[ecx*0x2F44+edx+0x48] -> returns record base. So at the CALL (after push ebx) the candidate list is dword record INDEXES at esp+0x18, bound = count (variable, >=1 because 0x471A13 returns 0 when empty). m1 0x414b90 calls the picker at 0x414bb4 and stores the result at [esi+4]. The m1 is called by the selector 0x418870 on every pass (phase select).',
            'note': "Stored at [event+4] by m1 0x414b90; m11 0x416A20: 'Wear it' -> Devotion +35 ([0x4980D8], 0x416A4D); 'Strainer' -> +200 food. m1 does `mov esi,ecx` before the picker call and the picker saves esi at 0x47187F, so at the site dword [esp+8] = the event object evaluating its condition (use it to tell slots apart when several slots share this m1). This m1 is shared by slots 5, 12, 35, 43, 45; the same scope_call evaluates their subjects too.",
        },
    ],
    46: [
        {
            'id': 'subject',
            'label': 'Who finds the nectar',
            'branch': None,
            'phase': 'select',
            'scope_call': 0x416AD7,
            'kind': 'victim',
            'site': 0x471A25,
            'candidates': {
                'base': {
                    'reg': 'esp',
                    'disp': 0x18,
                },
                'elem': 'index',
                'elem_disp': 0,
                'size': 4,
            },
            'filter': 'record in use (0x466170(0) at 0x4718A8), health [rec+0x1C40] > 0 (0x4718B5), not busy with activity 0xC..0x11 at [rec+0x1CFC] (a14=0, 0x471994..0x4719B6); believers only ([rec+0x1CEC]==0; a11=0,a13=0 -> 0x4719C2..0x4719CD); age [rec+0x1B8C] >= 0x168 (18 years; a1 -> 0x4718CE); pregnant and sick allowed',
            'evidence': 'Picker 0x471870 (thiscall ecx=0x554148, 14 args, ret 0x38): loops i=0..0x95 over records 0x554190+i*0x2F44 (esi=rec+0x1B8C), appends qualifying i to a stack list (0x4719E2 mov [esp+ebx*4+0x14],edi), then 0x471A24 push ebx(count) / 0x471A25 call rand / 0x471A2A mov ecx,[esp+eax*4+0x18] / 0x471A3E lea eax,[ecx*0x2F44+edx+0x48] -> returns record base. So at the CALL (after push ebx) the candidate list is dword record INDEXES at esp+0x18, bound = count (variable, >=1 because 0x471A13 returns 0 when empty). m1 0x416ab0 calls the picker at 0x416ad7 and stores the result at [esi+4]. The m1 is called by the selector 0x418870 on every pass (phase select).',
            'note': "Stored at [event+4] by m1 0x416ab0; m11 0x416B10: 'Drink it' -> that villager's age set to 0x14A (330 = 16.5 years, 0x416B2B). m1 does `mov esi,ecx` before the picker call and the picker saves esi at 0x47187F, so at the site dword [esp+8] = the event object evaluating its condition (use it to tell slots apart when several slots share this m1).",
        },
    ],
    47: [
        {
            'id': 'subject',
            'label': 'Who finds the broken mask',
            'branch': None,
            'phase': 'select',
            'scope_call': 0x415C65,
            'kind': 'victim',
            'site': 0x471A25,
            'candidates': {
                'base': {
                    'reg': 'esp',
                    'disp': 0x18,
                },
                'elem': 'index',
                'elem_disp': 0,
                'size': 4,
            },
            'filter': 'record in use (0x466170(0) at 0x4718A8), health [rec+0x1C40] > 0 (0x4718B5), not busy with activity 0xC..0x11 at [rec+0x1CFC] (a14=0, 0x471994..0x4719B6); believers only ([rec+0x1CEC]==0; a11=0,a13=0 -> 0x4719C2..0x4719CD); any age, any sex, pregnant and sick allowed',
            'evidence': 'Picker 0x471870 (thiscall ecx=0x554148, 14 args, ret 0x38): loops i=0..0x95 over records 0x554190+i*0x2F44 (esi=rec+0x1B8C), appends qualifying i to a stack list (0x4719E2 mov [esp+ebx*4+0x14],edi), then 0x471A24 push ebx(count) / 0x471A25 call rand / 0x471A2A mov ecx,[esp+eax*4+0x18] / 0x471A3E lea eax,[ecx*0x2F44+edx+0x48] -> returns record base. So at the CALL (after push ebx) the candidate list is dword record INDEXES at esp+0x18, bound = count (variable, >=1 because 0x471A13 returns 0 when empty). m1 0x415c40 calls the picker at 0x415c65 and stores the result at [esi+4]. The m1 is called by the selector 0x418870 on every pass (phase select).',
            'note': "Stored at [event+4] by m1 0x415c40; m11 0x416BB0: 'Attempt to fix' -> health loss and Devotion +25; 'Trick' -> SET_FAITH(-10,1) + SET_FACTION(1). m1 does `mov esi,ecx` before the picker call and the picker saves esi at 0x47187F, so at the site dword [esp+8] = the event object evaluating its condition (use it to tell slots apart when several slots share this m1). This m1 is shared by slots 34, 47; the same scope_call evaluates their subjects too.",
        },
        {
            'id': 'heathen',
            'label': 'Which heathen child owns the mask',
            'branch': None,
            'phase': 'select',
            'scope_call': 0x415C9D,
            'kind': 'victim',
            'site': 0x471A25,
            'candidates': {
                'base': {
                    'reg': 'esp',
                    'disp': 0x18,
                },
                'elem': 'index',
                'elem_disp': 0,
                'size': 4,
            },
            'filter': 'record in use (0x466170(0) at 0x4718A8), health [rec+0x1C40] > 0 (0x4718B5), not busy with activity 0xC..0x11 at [rec+0x1CFC] (a14=0, 0x471994..0x4719B6); heathens only ([rec+0x1CEC]!=0; a11=1 -> 0x471981); child: age [rec+0x1B8C] < 0x118 (14 years; a2 -> 0x4718E2); not sick (byte [rec+0x1C48]==0; a5=0 -> 0x471920); pregnant allowed',
            'evidence': 'Picker 0x471870 (thiscall ecx=0x554148, 14 args, ret 0x38): loops i=0..0x95 over records 0x554190+i*0x2F44 (esi=rec+0x1B8C), appends qualifying i to a stack list (0x4719E2 mov [esp+ebx*4+0x14],edi), then 0x471A24 push ebx(count) / 0x471A25 call rand / 0x471A2A mov ecx,[esp+eax*4+0x18] / 0x471A3E lea eax,[ecx*0x2F44+edx+0x48] -> returns record base. So at the CALL (after push ebx) the candidate list is dword record INDEXES at esp+0x18, bound = count (variable, >=1 because 0x471A13 returns 0 when empty). m1 0x415c40 calls the picker at 0x415c9d and stores the result at [esi+12]. The m1 is called by the selector 0x418870 on every pass (phase select).',
            'note': "Stored at [event+12] by m1 0x415c40; 'Attempt to fix the mask' (choice 0) gives that heathen child faith +35 (0x416C41; may convert). m1 does `mov esi,ecx` before the picker call and the picker saves esi at 0x47187F, so at the site dword [esp+8] = the event object evaluating its condition (use it to tell slots apart when several slots share this m1). This m1 is shared by slots 34, 47; the same scope_call evaluates their subjects too.",
        },
        {
            'id': 'health_lost',
            'label': 'If you fix the mask: health lost',
            'branch': 0,
            'phase': 'apply',
            'scope_call': None,
            'kind': 'amount',
            'site': 0x416C04,
            'bound': 11,
            'base': 20,
            'step': 1,
            'unit': 'health lost (20..30)',
            'evidence': "m11 0x416BB0: 0x416C02 push 0xB; 0x416C04 call rand; 0x416C09 ecx=-20-v; 0x416C1D HEALTH_ADD (cause -1) on the subject, choice 0 (button 'Attempt to fix the mask', id 2) only (0x416BF9 jne 0x416C4A). At <= 0 health is set to 0 with the cause, as stock can.",
        },
    ],
}

OMITTED = {
    6: [
        '0x47713C rand(30) -> [0x718EA0+0xC] = clock+60+v (type-4 periodic timer, re-rolled every cycle by the weather update at 0x477348) and 0x477156 rand(1000)/1000 intensity (only when [0x718EA0+8]==0): not durations; their gameplay effect was not traced -- left random',
    ],
    7: [
        '0x47713C rand(30) -> [0x718EA0+0xC] = clock+60+v (type-4 periodic timer, re-rolled every cycle by the weather update at 0x477348) and 0x477156 rand(1000)/1000 intensity (only when [0x718EA0+8]==0): not durations; their gameplay effect was not traced -- left random',
    ],
    11: ['no result roll: both branches fixed (m10 0x415680 text 0x39F/0x3A0)'],
    14: ['no result roll: both branches fixed (text 0x3BD/0x3BE)'],
    15: [
        '0x47713C rand(30) -> [0x718EA0+0xC] = clock+60+v (type-4 periodic timer, re-rolled every cycle by the weather update at 0x477348) and 0x477156 rand(1000)/1000 intensity (only when [0x718EA0+8]==0): not durations; their gameplay effect was not traced -- left random',
    ],
    26: [
        'no baby-count roll: always 3 attempts (0x415200/0x415243/0x415286 resp. 0x415440/0x415483/0x4154C6), fewer only when the village is full',
        "generic creation rolls inside shared 0x4681F0 (faith 30+rand(30) at 0x468508 -> SET_FAITH(v,0); likes/dislikes 0x46853C..0x46860A; head/body; 0x468650; spawn x/y 0x4687A3/0x4687B5): not requested for this pass; each could be scoped by the event's own CREATE call if wanted",
    ],
    27: [
        'no baby-count roll: always 3 attempts (0x4152E8/0x415333/0x41537E), fewer only when the village is full',
        'creation-routine faith roll 0x468508 is overwritten: 0x46FB80 calls SET_FAITH(a18=-55,1) at 0x46FC31 after 0x4681F0 -- not an outcome',
        "generic creation rolls inside shared 0x4681F0 (faith 30+rand(30) at 0x468508 -> SET_FAITH(v,0); likes/dislikes 0x46853C..0x46860A; head/body; 0x468650; spawn x/y 0x4687A3/0x4687B5): not requested for this pass; each could be scoped by the event's own CREATE call if wanted",
    ],
    30: [
        'no baby-count roll: always 3 attempts (0x415200/0x415243/0x415286 resp. 0x415440/0x415483/0x4154C6), fewer only when the village is full',
        "generic creation rolls inside shared 0x4681F0 (faith 30+rand(30) at 0x468508 -> SET_FAITH(v,0); likes/dislikes 0x46853C..0x46860A; head/body; 0x468650; spawn x/y 0x4687A3/0x4687B5): not requested for this pass; each could be scoped by the event's own CREATE call if wanted",
    ],
    31: [
        "generic creation rolls inside shared 0x4681F0 (faith 30+rand(30) at 0x468508 -> SET_FAITH(v,0); likes/dislikes 0x46853C..0x46860A; head/body; 0x468650; spawn x/y 0x4687A3/0x4687B5): not requested for this pass; each could be scoped by the event's own CREATE call if wanted",
    ],
    38: ['no result roll: both branches fixed (text 0x3E2/0x3E3)'],
    39: [
        "no result roll: 'Offer a tour' fixed (also food -25, tech -800); 'Refuse the tour' does nothing",
    ],
    41: [
        'no result roll: both branches fixed (+1500 tech / -100 food +3000 tech)',
    ],
    42: ['no result roll: both branches fixed'],
    43: ['no result roll: both branches fixed'],
    45: ['no result roll: both branches fixed'],
    46: ['no result roll: both branches fixed'],
}

COSMETIC = {
    2: [
        'sites 0x477F6C/0x477F9B/0x477FA4 (0x473440 -> 0x477DE0): random stop/walk spot for each villager whose activity is reset -- position only',
    ],
    3: [
        'sites 0x477F6C/0x477F9B/0x477FA4 (0x473440 -> 0x477DE0): random stop/walk spot for each villager whose activity is reset -- position only',
    ],
    4: [
        'sites 0x477F6C/0x477F9B/0x477FA4 (0x473440 -> 0x477DE0): random stop/walk spot for each villager whose activity is reset -- position only',
    ],
    5: [
        'site 0x471A25 via 0x467F90 -> 0x4668B0 -> picker call 0x4669B6: only tests whether any heathen remains (0x4669BB test eax) -- the picked villager is never used',
    ],
    6: [
        'sites 0x47ADA6/0x47ADB2 (0x477060 type 4 -> 0x475E40(0) -> 0x47ADA0, 1024 iterations): particle positions',
    ],
    7: [
        'sites 0x47ADA6/0x47ADB2 (0x477060 type 4 -> 0x475E40(0) -> 0x47ADA0, 1024 iterations): particle positions',
    ],
    10: [
        'sites 0x477F6C/0x477F9B/0x477FA4 (0x473440 -> 0x477DE0): random stop/walk spot for each villager whose activity is reset -- position only',
    ],
    11: [
        'sites 0x477F6C/0x477F9B/0x477FA4 (0x473440 -> 0x477DE0): random stop/walk spot for each villager whose activity is reset -- position only',
        'no roll: m11 calls 0x470920 (sets UI-selected villager [game+0x17E24] = [subject+0x1C94]) -- presentation',
    ],
    12: [
        'site 0x471A25 via 0x467F90 -> 0x4668B0 -> picker call 0x4669B6: only tests whether any heathen remains (0x4669BB test eax) -- the picked villager is never used',
        'no roll: m11 calls 0x470920 (sets UI-selected villager [game+0x17E24] = [subject+0x1C94]) -- presentation',
    ],
    13: [
        'site 0x471A25 via 0x467F90 -> 0x4668B0 -> picker call 0x4669B6: only tests whether any heathen remains (0x4669BB test eax) -- the picked villager is never used',
        'no roll: m11 calls 0x470920 (sets UI-selected villager [game+0x17E24] = [subject+0x1C94]) -- presentation',
    ],
    14: [
        'site 0x471A25 via scope 0x4159B5: second villager [event+0xC] (same filter) is only shown by the dialog (m8 0x4149D0 -> dlg+0x838); m11 never reads it',
        'no roll: m11 calls 0x470920 (sets UI-selected villager [game+0x17E24] = [subject+0x1C94]) -- presentation',
    ],
    15: [
        'sites 0x47ADA6/0x47ADB2 (0x477060 type 4 -> 0x475E40(0) -> 0x47ADA0, 1024 iterations): particle positions',
    ],
    19: [
        'sites 0x477F6C/0x477F9B/0x477FA4 (0x473440 -> 0x477DE0): random stop/walk spot for each villager whose activity is reset -- position only',
    ],
    20: [
        'sites 0x477F6C/0x477F9B/0x477FA4 (0x473440 -> 0x477DE0): random stop/walk spot for each villager whose activity is reset -- position only',
    ],
    24: [
        'site 0x471A25 via scope 0x4150D7: the child m1 0x4150B0 picks is never read by apply 0x4150F0 (text/UI only)',
        'sites 0x477F6C/0x477F9B/0x477FA4 (0x473440 -> 0x477DE0): random stop/walk spot for each villager whose activity is reset -- position only',
    ],
    28: [
        'sites 0x477F6C/0x477F9B/0x477FA4 (0x473440 -> 0x477DE0): random stop/walk spot for each villager whose activity is reset -- position only',
    ],
    30: [
        "sites 0x4712F3/0x47130D (0x471200 at 0x4154E8): onlookers' walk destinations",
        'sites 0x477F6C/0x477F9B/0x477FA4 (0x473440 -> 0x477DE0): random stop/walk spot for each villager whose activity is reset -- position only',
    ],
    34: [
        'site 0x471A25 via scope 0x415C9D: heathen child [event+0xC] is never read by m11 0x415CD0 (dialog only)',
        'site 0x471A25 via 0x467F90 -> 0x4668B0 -> picker call 0x4669B6: only tests whether any heathen remains (0x4669BB test eax) -- the picked villager is never used',
        'no roll: m11 calls 0x470920 (sets UI-selected villager [game+0x17E24] = [subject+0x1C94]) -- presentation',
    ],
    35: [
        'site 0x471A25 via 0x467F90 -> 0x4668B0 -> picker call 0x4669B6: only tests whether any heathen remains (0x4669BB test eax) -- the picked villager is never used',
        'no roll: m11 calls 0x470920 (sets UI-selected villager [game+0x17E24] = [subject+0x1C94]) -- presentation',
    ],
    36: [
        'site 0x471A25 via 0x467F90 -> 0x4668B0 -> picker call 0x4669B6: only tests whether any heathen remains (0x4669BB test eax) -- the picked villager is never used',
        'no roll: m11 calls 0x470920 (sets UI-selected villager [game+0x17E24] = [subject+0x1C94]) -- presentation',
    ],
    37: [
        'site 0x471A25 via scope 0x415FC0: heathen child [event+0xC] is never read by m11 0x416020 (dialog only)',
        'no roll: m11 calls 0x470920 (sets UI-selected villager [game+0x17E24] = [subject+0x1C94]) -- presentation',
    ],
    38: [
        'sites 0x41613C/0x416154/0x416174/0x41618C: walk-to x/y (0x4662C0/0x4662D0 set [rec+0x1C98]/[rec+0x1C9C])',
        'sites 0x477F6C/0x477F9B/0x477FA4 (0x473440 -> 0x477DE0): random stop/walk spot for each villager whose activity is reset -- position only',
        'site 0x471A25 via 0x467F90 -> 0x4668B0 -> picker call 0x4669B6: only tests whether any heathen remains (0x4669BB test eax) -- the picked villager is never used',
        'no roll: m11 calls 0x470920 (sets UI-selected villager [game+0x17E24] = [subject+0x1C94]) -- presentation',
    ],
    39: [
        'sites 0x416340/0x416358/0x416378/0x416390: walk-to x/y (0x4662C0/0x4662D0)',
        'sites 0x477F6C/0x477F9B/0x477FA4 (0x473440 -> 0x477DE0): random stop/walk spot for each villager whose activity is reset -- position only',
        'site 0x471A25 via 0x467F90 -> 0x4668B0 -> picker call 0x4669B6: only tests whether any heathen remains (0x4669BB test eax) -- the picked villager is never used',
        'no roll: m11 calls 0x470920 (sets UI-selected villager [game+0x17E24] = [subject+0x1C94]) -- presentation',
    ],
    41: [
        'no roll: m11 calls 0x470920 (sets UI-selected villager [game+0x17E24] = [subject+0x1C94]) -- presentation',
    ],
    42: [
        'sites 0x4712F3/0x47130D (0x471200 at 0x4167D6): group walk destinations',
        'sites 0x477F6C/0x477F9B/0x477FA4 (0x473440 -> 0x477DE0): random stop/walk spot for each villager whose activity is reset -- position only',
        'no roll: m11 calls 0x470920 (sets UI-selected villager [game+0x17E24] = [subject+0x1C94]) -- presentation',
    ],
    43: [
        'no roll: m11 calls 0x470920 (sets UI-selected villager [game+0x17E24] = [subject+0x1C94]) -- presentation',
    ],
    44: [
        'site 0x471A25 via 0x467F90 -> 0x4668B0 -> picker call 0x4669B6: only tests whether any heathen remains (0x4669BB test eax) -- the picked villager is never used',
        'no roll: m11 calls 0x470920 (sets UI-selected villager [game+0x17E24] = [subject+0x1C94]) -- presentation',
    ],
    45: [
        'no roll: m11 calls 0x470920 (sets UI-selected villager [game+0x17E24] = [subject+0x1C94]) -- presentation',
    ],
    46: [
        'no roll: m11 calls 0x470920 (sets UI-selected villager [game+0x17E24] = [subject+0x1C94]) -- presentation',
    ],
    47: [
        'sites 0x416BCB/0x416BE3: walk-to x/y (0x4662C0/0x4662D0)',
        'sites 0x477F6C/0x477F9B/0x477FA4 (0x473440 -> 0x477DE0): random stop/walk spot for each villager whose activity is reset -- position only',
        'site 0x471A25 via 0x467F90 -> 0x4668B0 -> picker call 0x4669B6: only tests whether any heathen remains (0x4669BB test eax) -- the picked villager is never used',
        'no roll: m11 calls 0x470920 (sets UI-selected villager [game+0x17E24] = [subject+0x1C94]) -- presentation',
    ],
    55: [
        'site 0x471A25 via scope 0x416FD9: which child the story names (text / UI selection only; m11 never changes it)',
        'sites 0x4712F3/0x47130D (0x471200 at 0x41704B/0x417076): walk destinations',
        'sites 0x41D557/0x41D564/0x41D581 (0x41D460 on 0x4DE000): particle effects',
        'sites 0x477F6C/0x477F9B/0x477FA4 (0x473440 -> 0x477DE0): random stop/walk spot for each villager whose activity is reset -- position only',
    ],
}

NO_OUTCOME = {
    1: 'No roll: prepare 0x414A00 amount = min(food [0x51D34C], 100); apply 0x414A30 subtracts it (0x41EB40).',
    2: 'No outcome roll: apply 0x414A70 gives activity 0x40 to every believer (0x470C60) and every heathen (0x470D60); the helpers pick no one by chance (0x470C80..0x470CEA collect all living matches, 0x470D20 loop applies to all); their only rolls are walk spots.',
    3: 'No outcome roll: apply 0x414AC0 gives activity 0x2F to every believer (0x470C60) and food +0 (0x41EB40(0)).',
    4: 'No outcome roll: apply 0x414DD0 gives activity 0x11 to every believer (0x470C60). Condition 0x414DB0: graves 0x464E90 >= 2.',
    8: 'Fixed: prepare 0x414CE0 amount 2000; apply 0x414CF0 sets weather 0x476F50(4) (no roll) and adds 2000 tech (0x4237B0).',
    9: 'Fixed: prepare 0x414D30 amount = min(tech [0x51D5F8], 2000); apply 0x414D60 sets weather 0x476F50(4) (no roll) and subtracts it.',
    10: 'No roll: apply 0x414B30 food +0, activity 0x2D to every believer (0x470C60), copies [0x425950()+0x17D60] to +0x17D64.',
    16: 'No roll: apply 0x414E80 sets the crop counter [0x425950()+0x17D5C] to 0.',
    17: 'No roll: apply 0x414EB0 halves the crop counter [0x425950()+0x17D5C] (signed /2).',
    19: 'No outcome roll: apply 0x414F30 gives activity 0xD1 (hide) to every believer (0x470C60).',
    20: 'No outcome roll: apply 0x414F70 gives activity 0x3A to every believer (0x470C60).',
    21: 'No roll: apply 0x414FB0 adds 200 to [0x425950()+0x17D58] and, if 0x43AE80(5) on 0x51E008 holds, 200 to [..+0x17D5C].',
    22: 'No roll: apply 0x415010 adds 200 to [0x425950()+0x17D58].',
    28: 'No outcome roll: apply 0x4153B0 gives activity 0xD1 (hide) to every believer (0x470C60) and every heathen (0x470D60).',
    32: 'No roll: apply 0x4155B0 adds 2000 tech points (0x4237B0(0x7D0)).',
    55: 'No outcome roll. The child picked by m1 0x416FA0 (picker call 0x416FD9 -> [event+4]) is only shown in the text and UI-selected (m11 0x417010 passes it only to 0x470920); both choices act on every child (0x471200 walk + 0x470C60 activity 0xDB/0xDA with age < 0x118) and spawn sparkle effects (0x41D460).',
}

EXTRA = {
    'picker': {
        'va': 0x471870,
        'rand_site': 0x471A25,
        'record_base': '0x554190 + index*0x2F44',
        'candidates_at_site': 'dword record indexes at [esp+0x18 + 4*i], count = bound (pushed ebx)',
        'event_this_at_site': {
            'mem': ['esp', 8],
            'disp': 0,
        },
        'args': 'a1 min age (>=), a2 max age (<), a3 sex, a4 allow pregnant ([rec+0x1C4C]), a5 allow sick (byte [rec+0x1C48]), a6/a7 skill index / minimum, a8 need pregnant, a9 need sick, a10 out count ptr, a11 heathen only ([rec+0x1CEC]!=0), a12 allow [rec+0x1D0C]!=-1, a13 allow heathen, a14 allow activity 0xC..0x11 at [rec+0x1CFC]',
        'shared_m1': {
            '0x414B90': [5, 12, 35, 43, 45],
            '0x415C40': [34, 47],
            '0x415E20': [36, 38],
        },
    },
    'no_loops': 'No offered VV5 event rolls a per-villager state change: 0x470C60/0x470D60 apply to every matching villager and their only rand calls are walk spots in 0x477DE0 (0x477F6C/0x477F9B/0x477FA4).',
}
