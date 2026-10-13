/* Is a bound custom title (native/shared/custom_titles.h) shown on a live
 * villager record?  The rule the log exporters print it by -- "VVFP
 * Population Export.dll" (Village Population, Village History) and "VVFP
 * Parentage Export.dll" (the custom title line of Death, Disappeared,
 * Unaccounted, Name changed records, and VillageCustomTitle for the Island
 * Events log) -- mirroring the Story / Cheat Upgrades companion
 * (native/vvfp_story_upgrades/story_titles.inc titles_could_be,
 * titles_candidates), which binds a title by record index AND fingerprint and
 * tells apart two villagers who share a fingerprint (twins with one name,
 * likes and dislikes) by the looks the entry keeps.
 *
 * Entry `e` is shown on record `r` exactly when:
 *   - it is bound (index != VV_TITLE_PENDING; a pending title is nobody's),
 *     its index is r, and record r has its fingerprint (vv_title_identity);
 *   - its looks are not known (a version 2 entry, flags without
 *     VV_TITLE_KNOWN): r is the only record that carries the fingerprint
 *     among the present records and r itself (two carriers and nothing else
 *     to tell them apart: nobody's -- a departing r with one present
 *     namesake is two);
 *   - its looks are known: exactly ONE record carries the fingerprint and has
 *     looks the entry's could be (custom_titles.h vv_title_looks_could_be:
 *     the same head, body and sex, no younger and no skill lower), and that
 *     one is r.  Identical twins (both could be) are nobody's -- never a
 *     guess; a stale file whose index now holds the other twin shows nothing
 *     there.
 *
 * "Present" is the exporters' own test: the record's live byte is 1 and it is
 * no look-alike (villager_lookalike.h) -- a body awaiting burial included.
 * Record r itself, the villager being written, is a candidate even when its
 * live byte was just cleared (a Disappeared record written as the villager
 * is taken): it is still the villager the entry is bound to.
 *
 * The looks are read at the record's own offsets, which the caller passes
 * (the same fields the Story companion's story_title_looks reads at its
 * adapters' off_age / off_head / off_body / off_sex / off_skills,
 * story_c1.inc .. story_c5.inc), skills normalised as custom_titles.h does
 * (vv_title_normalise_skills). */
#ifndef VV_CUSTOM_TITLE_SHOWN_H
#define VV_CUSTOM_TITLE_SHOWN_H

#include "custom_titles.h"
#include "villager_lookalike.h"

typedef struct {
    const unsigned char *first;     /* record 0 */
    unsigned int stride;
    unsigned int slots;
    unsigned int active;            /* u8, 1 = live */
    unsigned int name, name_capacity, likes, dislikes, preference_slots;
    unsigned int age, head, body, sex;
    unsigned int skills, skill_count;
    int skills_float;
} vv_title_table;

static const unsigned char *vv_title_table_record(const vv_title_table *t, unsigned int i) {
    return t->first + (size_t)i * t->stride;
}

static unsigned int vv_title_table_identity(const vv_title_table *t, const unsigned char *record) {
    return vv_title_identity(record, t->name, t->name_capacity, t->likes, t->dislikes, t->preference_slots);
}

static void vv_title_table_looks(const vv_title_table *t, const unsigned char *record, vv_title_looks *out) {
    unsigned int k;
    memset(out, 0, sizeof *out);
    out->age = *(const int *)(record + t->age);
    out->head = *(const int *)(record + t->head);
    out->body = *(const int *)(record + t->body);
    out->sex = *(const int *)(record + t->sex);
    for (k = 0; k < t->skill_count && k < VV_TITLE_SKILLS; ++k) {
        out->skills[k] = *(const unsigned int *)(record + t->skills + 4u * k);
    }
    vv_title_normalise_skills(out, t->skills_float);
}

static int vv_title_table_present(const vv_title_table *t, const unsigned char *record) {
    return *(const unsigned char *)(record + t->active) == 1 && !vv_lookalike(t->stride, record);
}

static int vv_title_shown_on(const vv_custom_title *e, const vv_title_table *t, unsigned int r) {
    unsigned int i;
    int carriers = 0;
    int could = 0;
    unsigned int where = 0;
    if (e->index == VV_TITLE_PENDING || e->index != r || r >= t->slots
        || vv_title_table_identity(t, vv_title_table_record(t, r)) != e->fingerprint) {
        return 0;
    }
    for (i = 0; i < t->slots; ++i) {
        const unsigned char *record = vv_title_table_record(t, i);
        int present = vv_title_table_present(t, record);
        if ((!present && i != r) || vv_title_table_identity(t, record) != e->fingerprint) {
            continue;
        }
        /* Every admitted record is a carrier -- record r too when its live
           byte was just cleared (a Disappeared record): the departing
           villager could still own the title, so one present namesake
           makes two carriers and a version 2 entry nobody's (Codex, #587). */
        ++carriers;
        if (e->flags & VV_TITLE_KNOWN) {
            vv_title_looks now;
            vv_title_table_looks(t, record, &now);
            if (vv_title_looks_could_be(&e->looks, &now, t->skills_float)) {
                ++could;
                where = i;
            }
        }
    }
    if (!(e->flags & VV_TITLE_KNOWN)) {
        return carriers <= 1;
    }
    return could == 1 && where == r;
}

#endif /* VV_CUSTOM_TITLE_SHOWN_H */
