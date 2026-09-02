"""Hybrid greedy + genetic algorithm timetable solver."""

import random
import time
from dataclasses import replace

from core.solver.fitness import evaluate_schedule, find_hard_violations
from core.solver.greedy import build_greedy_schedule
from core.solver.mutations import (
    crossover,
    day_swap,
    move_to_empty,
    swap_double,
    swap_within_class,
    swap_within_teacher,
)
from core.solver.problem import ScheduleEntry, SolverResult, TimetableProblem


class TimetableSolver:
    """Hybrid greedy + genetic algorithm timetable solver.

    Usage:
        problem = TimetableProblem(...)
        solver = TimetableSolver(problem)
        result = solver.solve(time_limit=60, population_size=50, generations=2000)
    """

    MUTATIONS = [
        swap_within_class,
        swap_within_teacher,
        move_to_empty,
        swap_double,
        day_swap,
    ]

    def __init__(self, problem: TimetableProblem):
        self.problem = problem

    def solve(
        self,
        time_limit: float = 60.0,
        population_size: int = 50,
        generations: int = 2000,
        plateau_limit: int = 200,
    ) -> SolverResult:
        """Run the solver. Returns the best result found within the time limit.

        1. Generate `population_size` initial schedules using greedy
           construction with randomized tie-breaking.
        2. Score each with the fitness function.
        3. For `generations` iterations (or until time_limit): tournament
           selection, crossover, mutation, keep-if-better replacement.
        4. Return the best individual found.
        """
        started = time.time()
        rng = random.Random(42)

        population: list[tuple[list[ScheduleEntry], float]] = []
        greedy_schedule, _failed = build_greedy_schedule(self.problem, rng)
        greedy_score, hard, soft = evaluate_schedule(self.problem, greedy_schedule)
        population.append((greedy_schedule, greedy_score))

        for _ in range(population_size - len(population)):
            candidate, _failed = build_greedy_schedule(self.problem, rng, relaxed=True)
            score, _hard, _soft = evaluate_schedule(self.problem, candidate)
            population.append((candidate, score))

        best_schedule = greedy_schedule
        best_score = greedy_score
        best_hard = hard
        best_soft = soft
        log_lines: list[str] = [f"greedy: score={greedy_score:.0f} hard={len(hard)}"]

        iterations = 0
        plateau = 0
        mutations = self.MUTATIONS

        for generation in range(1, generations + 1):
            iterations = generation
            if time.time() - started > time_limit:
                log_lines.append(f"gen {generation}: time limit reached")
                break

            parents = [self._tournament(population, rng) for _ in range(2)]
            child = crossover(self.problem, parents[0][0], parents[1][0], rng)

            for mutate in mutations:
                if rng.random() < 0.3:
                    mutated = mutate(self.problem, child, rng)
                    if mutated is not None:
                        child = mutated

            score, hard, soft = evaluate_schedule(self.problem, child)
            worst_index = max(range(len(population)), key=lambda i: population[i][1])
            if score > population[worst_index][1]:
                population[worst_index] = (child, score)

            if score > best_score:
                best_schedule = [replace(e) for e in child]
                best_score = score
                best_hard = hard
                best_soft = soft
                plateau = 0
            else:
                plateau += 1

            if generation % 100 == 0:
                log_lines.append(
                    f"gen {generation}: best={best_score:.0f} hard={len(best_hard)}"
                )

            if plateau >= plateau_limit:
                log_lines.append(f"gen {generation}: plateau Ã¢â‚¬â€ injecting fresh blood")
                for _ in range(10):
                    candidate, _failed = build_greedy_schedule(
                        self.problem, rng, relaxed=True
                    )
                    score, _h, _s = evaluate_schedule(self.problem, candidate)
                    population.append((candidate, score))
                population.sort(key=lambda item: item[1], reverse=True)
                population = population[:population_size]
                plateau = 0

        best_score, best_hard, best_soft = self._final_evaluate(best_schedule)
        generation_time = time.time() - started
        log_lines.append(f"final: score={best_score:.0f} in {generation_time:.1f}s")

        return SolverResult(
            schedule=best_schedule,
            fitness_score=best_score,
            hard_violations=best_hard,
            soft_violations=best_soft,
            generation_time_seconds=generation_time,
            iterations=iterations,
            solver_log="\n".join(log_lines),
            success=len(best_hard) == 0,
        )

    def _final_evaluate(self, schedule: list[ScheduleEntry]):
        from core.solver.fitness import evaluate_schedule as _eval

        score, hard, soft = _eval(self.problem, schedule)
        return score, hard, soft

    def _tournament(self, population, rng: random.Random, size: int = 3):
        contenders = rng.sample(population, min(size, len(population)))
        return max(contenders, key=lambda item: item[1])

    def _find_hard(self, schedule: list[ScheduleEntry]):
        return find_hard_violations(self.problem, schedule)
