build_tpm_tcpa(GArray *table_data, GArray *linker, GArray *tcpalog)

{

    Acpi20Tcpa *tcpa = acpi_data_push(table_data, sizeof *tcpa);

    uint64_t log_area_start_address = acpi_data_len(tcpalog);



    tcpa->platform_class = cpu_to_le16(TPM_TCPA_ACPI_CLASS_CLIENT);

    tcpa->log_area_minimum_length = cpu_to_le32(TPM_LOG_AREA_MINIMUM_SIZE);

    tcpa->log_area_start_address = cpu_to_le64(log_area_start_address);



    bios_linker_loader_alloc(linker, ACPI_BUILD_TPMLOG_FILE, 1,

                             false /* high memory */);



    /* log area start address to be filled by Guest linker */

    bios_linker_loader_add_pointer(linker, ACPI_BUILD_TABLE_FILE,

                                   ACPI_BUILD_TPMLOG_FILE,

                                   table_data, &tcpa->log_area_start_address,

                                   sizeof(tcpa->log_area_start_address));



    build_header(linker, table_data,

                 (void *)tcpa, "TCPA", sizeof(*tcpa), 2, NULL);



    acpi_data_push(tcpalog, TPM_LOG_AREA_MINIMUM_SIZE);

}
