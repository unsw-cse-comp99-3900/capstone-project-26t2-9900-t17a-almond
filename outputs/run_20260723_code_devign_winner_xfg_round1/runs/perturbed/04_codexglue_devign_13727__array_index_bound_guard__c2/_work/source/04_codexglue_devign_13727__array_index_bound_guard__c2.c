static void emulate_spapr_hypercall(CPUPPCState *env)

{

    if ((int)(3) >= 0 && (size_t)(3) < (sizeof(env->gpr) / sizeof((env->gpr)[0]))) {
        env->gpr[3] =spapr_hypercall(env, env->gpr[3], &env->gpr[4]);
    }

}
