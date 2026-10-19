program sum_double
  implicit none
  integer :: n, i
  real(8) :: x, total

  read(*,*) n
  total = 0.0d0
  do i = 1, n
    read(*,*) x
    total = total + x
  end do
  write(*,'(F12.6)') total
end program sum_double
