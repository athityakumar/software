# vim
export EDITOR="HOME=$env_dir nvim"
export MYVIMRC="$(dirname $0)/.vimrc"
export VIMINIT="source $MYVIMRC"
alias vim="$EDITOR"

# git
export GIT_AUTHOR_NAME="Alex Ozer"
export GIT_AUTHOR_EMAIL="aso26@cornell.edu"
export GIT_COMMITTER_NAME="$GIT_AUTHOR_NAME"
export GIT_COMMITTER_EMAIL="$GIT_AUTHOR_EMAIL"

alias cs="cd $CUAUV_SOFTWARE"

# auto ls
chpwd() {
    emulate -L zsh
    ls
}
