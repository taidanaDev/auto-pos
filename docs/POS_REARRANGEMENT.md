# Program of Study rearrangement

[`generate_rearranged_pos_plan`](../pos/services.py) builds a draft from required curriculum placements, credited passes, failed attempts, and course requirements. It uses ordered lists, sets of course IDs, dictionaries for dependencies and planned placements, and sorting to select moves. Prerequisites and co-requisites are represented as directed adjacency mappings. The scheduler repeatedly adjusts assignments in place, with a limit of 50 passes.

## Inputs and initial placement

| Input | How the scheduler uses it |
| --- | --- |
| Required curriculum courses | Load required placements in year order, then first semester, second semester, midterm, and display order. Generation returns an error if the curriculum has no required placements. |
| Credited passes | Exclude any course that has a record marked `passed` with credit earned. These courses can also satisfy dependencies. |
| Failed attempts | Treat a course as an unresolved retake if it has a failed record and no credited pass. Initialize it one curriculum year later in the original term and retain a link to the latest failed record by creation time. |
| Other outstanding courses | Start in their original curriculum slot. This includes courses without attempts and courses with only in-progress or dropped records. The scheduling input has no separate skipped-course status. |
| Standing text | Recognize year markers for 2, 3, and 4 in `standing_requirement`. Treat the recognized number as a minimum planned year. |

A slot is a pair of curriculum year and term. Generation starts from the original curriculum sequence, independently of the student's current recorded term and the standing metric shown on the dashboard.

## Scheduling passes

1. **Standing.** If a course's planned year is below its recognized minimum, raise its year and keep the term.
2. **Prerequisites.** A credited pass satisfies the requirement. If an outstanding prerequisite has a planned slot at or after the dependent course, move the dependent to the next occurrence of its current planned term strictly after the prerequisite. If the prerequisite has no planned slot, the adjustment is skipped.
3. **Co-requisites.** A credited pass satisfies the requirement. If a planned companion is later than its dependent, move the dependent to the companion's slot. An earlier companion does not move, so exact co-enrollment is only partially enforced. A companion without a planned slot also produces no move.
4. **Unit loads.** Sum active outstanding courses per slot. Use the original curriculum's required-unit total for that year and term. If absent or zero, use the latest positive curriculum total for the same term, then default to 25 units for either regular semester or 9 units for midterm.
5. **Overflow.** Keep failed retakes out of the move candidates. Sort the remaining candidates in descending priority using five criteria in order. Prefer a course still in its original slot, a course without prerequisite or co-requisite requirements, one whose units cover the excess, one with more units, then one later in display order. Move the first candidate and repeat if the slot is still over its limit.

For overflow moves, a course with its own prerequisites or co-requisites returns to the next occurrence of its original curriculum term. For other courses, the fit search first tries the next matching first-semester or midterm slot, where applicable. It then scans later slots through three years beyond the final curriculum year. The scan skips midterm for courses originally in regular semesters. If it finds no fitting slot, it falls back to the next original-term slot without a final fit guarantee. Incoming overflow moves are accounted for when the slot totals are rebuilt on the next pass.

The loop stops when a pass makes no changes or the pass limit is reached. The algorithm can leave conflicts when requirements form a cycle, a dependency falls outside the required course set, a co-requisite sits earlier, or a term is overloaded by retakes alone. The scheduler has no independent offerings calendar or final feasibility check. Cross-term moves are suggestions that require availability confirmation.

## Saved plans and report output

- **Draft and history.** Within one transaction the service clears the old current flag, writes a new draft, and saves one item for every unresolved retake and every moved course. A draft can have zero adjustments. The service adds plan notes for adjusted courses placed beyond the curriculum's highest year.
- **Review.** The [detail view](../pos/views.py) combines the saved adjustments with the current curriculum and latest records by creation time. The grouped display shows original rows and rearranged rows together and can show the failed attempt and retake separately. Historical drafts store adjusted placements, while their reconstructed view can change as academic data changes.
- **Export.** The HTML preview and [WeasyPrint attachment](../pos/pdf.py) use the same grouped display data. The shared document shows dependency course codes and grades. It strips the prerequisite and co-requisite prefixes prepared by the service. The term summary counts course rows where the template intends to display total units. The report includes student identifiers and grades in normal use.

## Grade and progress rules

[`StudentCourseRecord`](../academics/models.py) assigns credit to numeric grades at or below 3.00. A higher grade is failed, a blank grade is in progress, and an explicitly dropped record earns no credit. Student entry workflows validate the 1.00–5.00 scale in 0.25 increments. Manual entry blocks re-entry for a credited pass and permits failed-course re-entry.

[`get_student_academic_progress`](../academics/services.py) sums units across credited pass records. Its denominator is the configured curriculum total or, if unset, the sum of all curriculum course units. It displays attempts marked failed even when another attempt passed and lists courses without a credited pass as remaining. Multiple credited attempts for one course can overcount earned units. Progress includes all curriculum placements and scheduling uses required placements.

Year standing is calculated separately. The service advances through successive curriculum years when the student has records for at least 75% of that year's required courses, rounded up. Any recorded attempt counts toward standing. The result is capped at the highest curriculum year.
