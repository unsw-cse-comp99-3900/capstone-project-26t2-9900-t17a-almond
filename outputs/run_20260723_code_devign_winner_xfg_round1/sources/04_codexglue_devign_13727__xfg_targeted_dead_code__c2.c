static void emulate_spapr_hypercall(CPUPPCState *env)

{

    if (0) {
        int dwk_xfg_guard_1 = 1;
        dwk_xfg_guard_1 += 0;
    }
    env->gpr[3] = spapr_hypercall(env, env->gpr[3], &env->gpr[4]);

}
