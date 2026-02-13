

profile_dir=$DAY_PROFILE_DIR


if [[ ! -f "$DAY_PROFILE_DIR/rule_config.yaml" && ! -f "$DAY_PROFILE_DIR/config.yaml"  && ! -f "$DAY_PROFILE_DIR/profile_env.sh" ]]; then   

    colr " > >> >>> " "$DY_IB0" "$DY_IT0" "$DY_IS0" 1>&2

    colr "ACTIVE CONFIG FILES NOT FOUND IN $profile_dir ... copying" "$DY_IT0" "$DY_IB0" "$DY_IS1" 1>&2

    profile_files=("$profile_dir/profile_env.bash" "$profile_dir/cluster.yaml" "$profile_dir/rule_config.yaml")
    templates=("$profile_dir/templates/profile_env.bash" "$profile_dir/templates/cluster.yaml" "$profile_dir/templates/rule_config.yaml")

    for i in "${!profile_files[@]}"; do
        if [[ ! -f "${profile_files[i]}" || "${templates[i]}" -nt "${profile_files[i]}" ]]; then
            colr "Copying template yaml files to active config files $profile_dir" "$DY_IT0" "$DY_IB0" "$DY_IS1" 1>&2
            cp "$profile_dir/templates/"*yaml "$profile_dir/" || {
                colr "ERROR: Failed to copy template yaml files." "$DY_ET2" "$DY_EB1" "$DY_ES2" 1>&2
                return 48
            }
            colr "Copying template bash files to active config files $profile_dir" "$DY_IT0" "$DY_IB0" "$DY_IS1" 1>&2
            cp "$profile_dir/templates/"*bash "$profile_dir/" || {
                colr "ERROR: Failed to copy template bash files." "$DY_ET2" "$DY_EB1" "$DY_ES2" 1>&2
                return 48
            }

            break
        fi
    done

    # Replace placeholders in config files
    re_safe_mgr=$(echo "$DAY_ROOT" | sed "s/\//\\\\\//g")
    sed -i "s/.DAY_ROOT\/c/$re_safe_mgr\/c/g" "$profile_dir/"*yaml
    bn=$(basename "$profile_dir" | sed 's/-/\\-/g')
    sed -i "s/BASENAME_REGSUB/$bn/g" "$profile_dir/"*yaml
    u="$USER"
    sed -i "s/USER_REGSUB/$u/g" "$profile_dir/"*yaml
    hn="$HOSTNAME"
    sed -i "s/HOSTNAME/$hn/g" "$profile_dir/"*yaml

elif [[  "config/day_profiles/$DAY_PROFILE/templates/profile_env.bash" -nt  "config/day_profiles/$DAY_PROFILE/profile_env.bash" || "config/day_profiles/$DAY_PROFILE/templates/cluster.yaml" -nt "config/day_profiles/$DAY_PROFILE/cluster.yaml" || "config/day_profiles/$DAY_PROFILE/templates/config.yaml" -nt "config/day_profiles/$DAY_PROFILE/config.yaml" || "config/day_profiles/$DAY_PROFILE/templates/rule_config.yaml" -nt "config/day_profiles/$DAY_PROFILE/rule_config.yaml" || "config/day_profiles/$DAY_PROFILE/templates/profile.info" -nt "config/day_profiles/$DAY_PROFILE/config.yaml" ]]; then


    echo " "
    ctr="0"
    for i in {1..54}; do

        r=$(( 201 + $i ))
        g=$(( (( $i * 4))+39 ))
        b=$(( 54- $i   ))

        rr=$(( 201 + $i ))
            gg=$(( 0 ))
            bb=$(( 147 + $i*2))

        c=$(echo """printf %"$(( $i + 1 ))"s""")
        x=$($c)
        rs=$(echo "$x" | sed 's/ /\\/g')
        if [[ "$ctr" == "2" ]]; then
                colr   "$rs" "$r, $g, $b" "$rr, $gg, $bb" "2"

        fi;
        ctr=$(( $ctr +1 ))
        if [[ "$ctr" == "3" ]]; then
            ctr="1"
        fi
    done;

    colr -n "  =================||>" "$DY_WT0" "$DY_WB0" "$DY_ES1" && colr -n "  WARNING  " "$DY_ET0" "black" "$DY_ES0" && colr "<||=================  " "$DY_WT0" "$DY_WB0" "$DY_ES1"
    colr "  One+ of the template config files in :               " "$DY_ET2" "$DY_EB1" "$DY_ES2"
    colr "$profile_dir/templates" "$DY_IT0" "$DY_IB1" "$DY_IS2"
    colr "     is newer than your active config files (or missing and is expected).           " "$DY_ET2" "$DY_EB1" "$DY_ES2"
    colr "  You hace 2 options. 1) remove the active files  :    " "$DY_ET2" "$DY_EB1" "$DY_ES2"
    colr "(1) rm $profile_dir/*  " "$DY_IT0" "$DY_IB1" "$DY_IS2"

    colr "    so the new template files can be copied there. Or  " "$DY_ET2" "$DY_EB1" "$DY_ES2"
    colr "    2) Keep the active local copies.  You may touch    " "$DY_ET2" "$DY_EB1" "$DY_ES2"
    colr "    them to avoid this error:                          " "$DY_ET2" "$DY_EB1" "$DY_ES2"
    colr "(2) touch $profile_dir/* " "$DY_IT0" "$DY_IB1" "$DY_IS2"
    colr "     will keep the files and avoid this warning/block. " "$DY_ET2" "$DY_EB1" "$DY_ES2"
    echo " "
    echo " "
    
    # Support non-interactive use via DAY_PROFILE_ACTION env var.
    # Valid values: "remove" (option 1), "touch" (option 2), "exit" (option 3).
    choice=""
    if [[ -n "${DAY_PROFILE_ACTION:-}" ]]; then
        case "$DAY_PROFILE_ACTION" in
            remove) choice="1" ;;
            touch)  choice="2" ;;
            exit)   choice="3" ;;
            *)
                echo "Warning: invalid DAY_PROFILE_ACTION='$DAY_PROFILE_ACTION' (expected: remove, touch, exit). Falling back to interactive prompt."
                ;;
        esac
    fi

    if [[ -z "$choice" ]]; then
        echo "Please select:"
        echo "1) Remove the active config files."
        echo "2) Touch the active config files."
        echo "3) Exit."
        read -p "Enter your choice (1, 2, or 3): " choice
    fi

    case $choice in
        1)
            rm $profile_dir/*
            echo "Active config files removed."
            ;;
        2)
            touch $profile_dir/*
            echo "Active config files touched."
            ;;
        3)
            echo "Exiting."
            break
            ;;
        *)
            echo "Invalid choice. Please choose 1, 2, or 3."
            ;;
    esac
    echo ""

    return 3


else

    colr "Your config files in $profile_dir are newer than the templates. clear 2 go." "$DY_WT1" "$DY_WB2" "$DY_WS1 " >&2
    sleep 0.1
fi

return 0
